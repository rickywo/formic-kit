#!/usr/bin/env python3
"""formic-kit board tool.

Safe reads and writes of <project>/.formic/board.json for the coordinator.

This tool guards the integrity of the board: schema, allowed status
transitions, task ids, file leases, backups and atomic writes. It does not
decide anything. Which task runs next, when to retry, and when to unblock a
task are decisions the coordinator makes by following the formic-coordinate
skill.

Python 3.8+, standard library only.
"""

import argparse
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 2

STATUSES = [
    "todo", "queued", "blocked",
    "briefing", "planning", "declaring", "running", "verifying", "architecting",
    "review", "done",
]
ACTIVE = {"briefing", "planning", "declaring", "running", "verifying", "architecting"}
PRIORITIES = ["high", "medium", "low"]
TYPES = ["standard", "quick", "goal"]
TIERS = ["haiku", "sonnet"]

# Allowed status changes. Any status may also go to "todo" (stop or park).
TRANSITIONS = {
    "todo": {"queued"},
    "blocked": {"queued"},
    "queued": {"briefing", "planning", "declaring", "running", "architecting"},
    "briefing": {"planning", "queued"},
    "planning": {"declaring", "queued"},
    "declaring": {"running", "queued"},
    "running": {"verifying", "queued"},
    "verifying": {"review", "running", "queued"},
    "architecting": {"review", "queued"},
    "review": {"done"},
    "done": set(),
}

SETTABLE = {
    "title": str,
    "priority": PRIORITIES,
    "type": TYPES,
    "executeTier": TIERS + [None],
    "workflowStep": str,
    "safePointCommit": str,
    "yieldReason": str,
    "retryCount": int,
    "yieldCount": int,
    "executeRounds": int,
}

V1_DROP = [
    "agentLogs", "pid", "workflowLogs", "leaseExpiresAt", "recoveryCount",
    "progress", "hasManualSubtasks", "dependsOnResolved", "resumeFromStep",
]

EXIT_ERROR = 1
EXIT_LEASE_CONFLICT = 3


class BoardError(Exception):
    pass


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def slugify(title):
    s = re.sub(r"[^a-z0-9\s-]", "", title.lower())
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s[:30].strip("-")


# ---------------------------------------------------------------- locations

def find_root(explicit):
    if explicit:
        root = Path(explicit).resolve()
        if not root.is_dir():
            raise BoardError(f"--root {root} is not a directory")
        return root
    cur = Path.cwd().resolve()
    for d in [cur, *cur.parents]:
        if (d / ".formic").is_dir():
            return d
    raise BoardError("no .formic/ folder found here or in any parent; run 'board.py init' in the project root")


def board_path(root):
    return root / ".formic" / "board.json"


# ------------------------------------------------------------------ locking

class Lock:
    """Short-lived lock so two board.py runs cannot interleave a write."""

    def __init__(self, root):
        self.path = root / ".formic" / "board.lock"
        self.held = False

    def __enter__(self):
        deadline = time.time() + 10
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, f"{os.getpid()} {now()}\n".encode())
                os.close(fd)
                self.held = True
                return self
            except FileExistsError:
                try:
                    if time.time() - self.path.stat().st_mtime > 60:
                        self.path.unlink()
                        continue
                except FileNotFoundError:
                    continue
                if time.time() > deadline:
                    raise BoardError(f"board is locked by another process ({self.path}); try again")
                time.sleep(0.1)

    def __exit__(self, *exc):
        if self.held:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass


# --------------------------------------------------------------- read/write

def load(root, allow_v1=False):
    p = board_path(root)
    if not p.exists():
        raise BoardError(f"{p} does not exist; run 'board.py init'")
    try:
        board = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        raise BoardError(f"{p} is not valid JSON ({e}). Restore from {p}.backup before doing anything else.")
    version = (board.get("meta") or {}).get("schemaVersion")
    if version != SCHEMA_VERSION and not allow_v1:
        raise BoardError(
            f"{p} has schemaVersion {version!r}, this tool needs {SCHEMA_VERSION}. Run 'board.py migrate'."
        )
    return board


def save(root, board):
    problems = check(root, board)
    if problems:
        raise BoardError("refusing to write an invalid board:\n  - " + "\n  - ".join(problems))
    p = board_path(root)
    if p.exists():
        shutil.copy2(p, p.with_name("board.json.backup"))
    tmp = p.with_name("board.json.tmp")
    with open(tmp, "w") as f:
        json.dump(board, f, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)


def check(root, board):
    """Return a list of problems; empty means the board is valid."""
    out = []
    meta = board.get("meta")
    if not isinstance(meta, dict):
        return ["meta is missing"]
    if meta.get("schemaVersion") != SCHEMA_VERSION:
        out.append(f"meta.schemaVersion must be {SCHEMA_VERSION}")
    for k in ("projectName", "createdAt"):
        if not isinstance(meta.get(k), str):
            out.append(f"meta.{k} must be a string")
    if not isinstance(meta.get("nextTaskId"), int):
        out.append("meta.nextTaskId must be a number")
    tasks = board.get("tasks")
    if not isinstance(tasks, list):
        return out + ["tasks must be a list"]

    ids = set()
    max_n = 0
    for t in tasks:
        tid = t.get("id")
        where = f"task {tid!r}"
        if not isinstance(tid, str) or not re.fullmatch(r"t-(\d+|bootstrap)", tid):
            out.append(f"{where}: id must look like t-12")
            continue
        if tid in ids:
            out.append(f"{where}: duplicate id")
        ids.add(tid)
        m = re.fullmatch(r"t-(\d+)", tid)
        if m:
            max_n = max(max_n, int(m.group(1)))
        if not t.get("title") or not isinstance(t.get("title"), str):
            out.append(f"{where}: title is empty")
        if not isinstance(t.get("context"), str):
            out.append(f"{where}: context must be a string")
        if t.get("status") not in STATUSES:
            out.append(f"{where}: unknown status {t.get('status')!r}")
        if t.get("priority") not in PRIORITIES:
            out.append(f"{where}: unknown priority {t.get('priority')!r}")
        if t.get("type") not in TYPES:
            out.append(f"{where}: unknown type {t.get('type')!r}")
        if t.get("executeTier") not in TIERS + [None]:
            out.append(f"{where}: executeTier must be haiku, sonnet or null")
        if not isinstance(t.get("docsPath"), str) or not t["docsPath"].startswith(".formic/tasks/"):
            out.append(f"{where}: docsPath must be under .formic/tasks/")
        if not isinstance(t.get("history"), list):
            out.append(f"{where}: history must be a list")
        leases = t.get("leases")
        if not isinstance(leases, dict) or not all(isinstance(leases.get(k), list) for k in ("exclusive", "shared")):
            out.append(f"{where}: leases must be {{exclusive: [], shared: []}}")
        elif (leases["exclusive"] or leases["shared"]) and t.get("status") not in ACTIVE:
            out.append(f"{where}: holds leases but status {t.get('status')!r} is not active")
        if t.get("agent") is not None and t.get("status") not in ACTIVE:
            out.append(f"{where}: has an agent recorded but status {t.get('status')!r} is not active")

    if isinstance(meta.get("nextTaskId"), int) and meta["nextTaskId"] <= max_n:
        out.append(f"meta.nextTaskId ({meta['nextTaskId']}) must be above the highest task id ({max_n})")

    for t in tasks:
        for dep in t.get("dependsOn") or []:
            if dep not in ids:
                out.append(f"task {t.get('id')!r}: dependsOn unknown task {dep}")
        if t.get("parentGoalId") and t["parentGoalId"] not in ids:
            out.append(f"task {t.get('id')!r}: parentGoalId {t['parentGoalId']} does not exist")

    for c in lease_conflicts_all(tasks):
        out.append(c)
    return out


def lease_conflicts_all(tasks):
    out = []
    excl = {}
    for t in tasks:
        for f in (t.get("leases") or {}).get("exclusive", []):
            if f in excl:
                out.append(f"file {f} is leased exclusively by both {excl[f]} and {t['id']}")
            excl[f] = t["id"]
    for t in tasks:
        for f in (t.get("leases") or {}).get("shared", []):
            if f in excl and excl[f] != t["id"]:
                out.append(f"file {f} is shared by {t['id']} but leased exclusively by {excl[f]}")
    return out


def get(board, tid):
    for t in board["tasks"]:
        if t["id"] == tid:
            return t
    raise BoardError(f"no task {tid} on the board")


def record(task, frm, to, note):
    task["history"].append({"at": now(), "from": frm, "to": to, "note": note or ""})


# ----------------------------------------------------------------- TASK.md

def write_task_md(root, task):
    """Snapshot of the task for workers, so they never need to read board.json."""
    d = root / task["docsPath"]
    d.mkdir(parents=True, exist_ok=True)
    (d / "output").mkdir(exist_ok=True)
    lines = [
        f"# {task['title']}",
        "",
        "Written by the coordinator from the board. Do not edit; changes here are overwritten.",
        "",
        f"- Task id: {task['id']}",
        f"- Type: {task['type']}",
        f"- Priority: {task['priority']}",
        f"- Execute tier: {task.get('executeTier') or 'not set'}",
    ]
    if task.get("parentGoalId"):
        lines.append(f"- Parent goal: {task['parentGoalId']}")
    if task.get("fixForTaskId"):
        lines.append(f"- Fix for: {task['fixForTaskId']}")
    if task.get("dependsOn"):
        lines.append(f"- Depends on: {', '.join(task['dependsOn'])}")
    lines += ["", "## Context", "", task["context"].rstrip(), ""]
    (d / "TASK.md").write_text("\n".join(lines))


# ---------------------------------------------------------------- commands

def cmd_init(args):
    root = Path(args.root).resolve() if args.root else Path.cwd().resolve()
    p = board_path(root)
    if p.exists():
        raise BoardError(f"{p} already exists; not touching it")
    (root / ".formic" / "tasks").mkdir(parents=True, exist_ok=True)
    board = {
        "meta": {
            "schemaVersion": SCHEMA_VERSION,
            "projectName": args.name or root.name,
            "createdAt": now(),
            "nextTaskId": 1,
        },
        "tasks": [],
    }
    with Lock(root):
        save(root, board)
    print(f"created {p}")


def cmd_validate(args):
    root = find_root(args.root)
    board = load(root)
    problems = check(root, board)
    if problems:
        print("INVALID")
        for p in problems:
            print(f"  - {p}")
        sys.exit(EXIT_ERROR)
    print(f"OK: {len(board['tasks'])} tasks, schemaVersion {SCHEMA_VERSION}")


def cmd_migrate(args):
    root = find_root(args.root)
    with Lock(root):
        board = load(root, allow_v1=True)
        meta = board.get("meta") or {}
        if meta.get("schemaVersion") == SCHEMA_VERSION:
            print("already at schemaVersion 2; nothing to do")
            return
        p = board_path(root)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        keep = p.with_name(f"board.json.v1-{stamp}")
        shutil.copy2(p, keep)

        max_n = 0
        requeued = []
        for t in board.get("tasks", []):
            m = re.fullmatch(r"t-(\d+)", t.get("id", ""))
            if m:
                max_n = max(max_n, int(m.group(1)))
            resolved = t.get("dependsOnResolved") or []
            for k in V1_DROP:
                t.pop(k, None)
            t["dependsOn"] = resolved
            t.setdefault("type", "standard")
            t.setdefault("priority", "medium")
            t.setdefault("context", "")
            t["executeTier"] = t.get("executeTier")
            t["retryCount"] = t.get("retryCount") or 0
            t["yieldCount"] = t.get("yieldCount") or 0
            t["executeRounds"] = 0
            t["leases"] = {"exclusive": [], "shared": []}
            t["agent"] = None
            old = t.get("status")
            if old in ACTIVE:
                t["status"] = "queued"
                requeued.append(t["id"])
            t["history"] = [{"at": now(), "from": None, "to": t["status"],
                             "note": f"migrated from Formic server board (was {old})"}]
        board["meta"] = {
            "schemaVersion": SCHEMA_VERSION,
            "projectName": meta.get("projectName") or root.name,
            "createdAt": meta.get("createdAt") or now(),
            "nextTaskId": max(int(meta.get("nextTaskId") or 0), max_n + 1),
        }
        save(root, board)
        for t in board["tasks"]:
            if (root / t["docsPath"]).is_dir() or t["status"] in ("todo", "queued", "blocked"):
                write_task_md(root, t)
    print(f"migrated {len(board['tasks'])} tasks to schemaVersion 2")
    print(f"original kept at {keep}")
    if requeued:
        print(f"tasks that were mid-run and are now queued: {', '.join(requeued)}")


def dep_summary(board, task):
    parts = []
    for dep in task.get("dependsOn") or []:
        try:
            parts.append(f"{dep}({get(board, dep)['status']})")
        except BoardError:
            parts.append(f"{dep}(missing)")
    return " ".join(parts)


def cmd_list(args):
    root = find_root(args.root)
    board = load(root)
    tasks = board["tasks"]
    if args.status:
        tasks = [t for t in tasks if t["status"] in args.status]
    if args.active:
        tasks = [t for t in tasks if t["status"] in ACTIVE]
    if args.json:
        slim = []
        for t in tasks:
            s = {k: v for k, v in t.items() if k not in ("context", "history")}
            slim.append(s)
        print(json.dumps(slim, indent=2))
        return
    if not tasks:
        print("(no tasks)")
        return
    for t in tasks:
        bits = [
            t["id"].ljust(6), t["status"].ljust(12), t["type"].ljust(8),
            t["priority"].ljust(6), (t.get("executeTier") or "-").ljust(6),
            f"retry={t.get('retryCount', 0)} yield={t.get('yieldCount', 0)}",
        ]
        if t.get("fixForTaskId"):
            bits.append(f"fix-for={t['fixForTaskId']}")
        if t.get("parentGoalId"):
            bits.append(f"goal={t['parentGoalId']}")
        deps = dep_summary(board, t)
        if deps:
            bits.append(f"deps=[{deps}]")
        n = len(t["leases"]["exclusive"]) + len(t["leases"]["shared"])
        if n:
            bits.append(f"leases={n}")
        if t.get("agent"):
            bits.append(f"agent={t['agent'].get('name')}@{t['agent'].get('paneId')}")
        bits.append(f"queued={t.get('queuedAt') or '-'}")
        print("  ".join(bits))
        print(f"       {t['title']}")


def cmd_show(args):
    root = find_root(args.root)
    board = load(root)
    print(json.dumps(get(board, args.id), indent=2))


def read_context(args):
    if getattr(args, "context_file", None):
        return Path(args.context_file).read_text()
    if getattr(args, "context", None) is not None:
        return args.context
    return None


def cmd_add(args):
    root = find_root(args.root)
    context = read_context(args)
    if context is None or not context.strip():
        raise BoardError("a task needs a context: pass --context or --context-file")
    if not args.title.strip():
        raise BoardError("title is empty")
    with Lock(root):
        board = load(root)
        ids = {t["id"] for t in board["tasks"]}
        deps = [d for d in (args.depends_on or "").split(",") if d]
        for d in deps:
            if d not in ids:
                raise BoardError(f"--depends-on {d}: no such task")
        if args.parent and args.parent not in ids:
            raise BoardError(f"--parent {args.parent}: no such task")
        if args.fix_for and args.fix_for not in ids:
            raise BoardError(f"--fix-for {args.fix_for}: no such task")
        status = args.status
        if deps and status != "blocked":
            raise BoardError("a task with --depends-on must be created with --status blocked")

        max_n = max([int(m.group(1)) for m in (re.fullmatch(r"t-(\d+)", i) for i in ids) if m] or [0])
        n = max(board["meta"]["nextTaskId"], max_n + 1)
        tid = f"t-{n}"
        board["meta"]["nextTaskId"] = n + 1
        ts = now()
        task = {
            "id": tid,
            "title": args.title.strip(),
            "context": context,
            "type": args.type,
            "priority": args.priority,
            "executeTier": args.tier,
            "status": status,
            "docsPath": f".formic/tasks/{tid}_{slugify(args.title)}",
            "workflowStep": "pending",
            "createdAt": ts,
            "queuedAt": ts if status == "queued" else None,
            "startedAt": None,
            "completedAt": None,
            "parentGoalId": args.parent,
            "childTaskIds": [],
            "dependsOn": deps,
            "fixForTaskId": args.fix_for,
            "declaredFiles": None,
            "leases": {"exclusive": [], "shared": []},
            "agent": None,
            "safePointCommit": None,
            "retryCount": 0,
            "yieldCount": 0,
            "executeRounds": 0,
            "yieldReason": None,
            "history": [],
        }
        record(task, None, status, args.note or "created")
        board["tasks"].append(task)
        if args.parent:
            get(board, args.parent)["childTaskIds"].append(tid)
        save(root, board)
        write_task_md(root, task)
    print(json.dumps({"id": tid, "status": status, "docsPath": task["docsPath"]}))


def cmd_move(args):
    root = find_root(args.root)
    to = args.status
    with Lock(root):
        board = load(root)
        t = get(board, args.id)
        frm = t["status"]
        if frm == to:
            raise BoardError(f"{t['id']} is already {to}")
        allowed = to == "todo" or to in TRANSITIONS[frm]
        if not allowed and not args.force:
            ok = sorted(TRANSITIONS[frm] | {"todo"})
            raise BoardError(
                f"{t['id']}: {frm} -> {to} is not an allowed transition. From {frm} you can go to: {', '.join(ok)}. "
                "Use --force with --note only to repair a board by hand."
            )
        if args.force and not args.note:
            raise BoardError("--force needs --note explaining why")
        if to == "queued" and frm in ("todo", "blocked"):
            unmet = [d for d in t.get("dependsOn") or [] if get(board, d)["status"] not in ("review", "done")]
            if unmet and not args.force:
                raise BoardError(f"{t['id']} still depends on: {', '.join(unmet)} (not yet in review or done)")

        ts = now()
        released = []
        if frm in ACTIVE and to not in ACTIVE:
            released = t["leases"]["exclusive"] + t["leases"]["shared"]
            t["leases"] = {"exclusive": [], "shared": []}
            t["agent"] = None
        if to in ACTIVE and not t.get("startedAt"):
            t["startedAt"] = ts
        if to == "queued":
            t["queuedAt"] = ts
            if frm in ("todo", "blocked"):
                t["retryCount"] = 0
                t["yieldCount"] = 0
                t["executeRounds"] = 0
                t["yieldReason"] = None
        if to in ("review", "done"):
            t["completedAt"] = ts
        if to == "todo":
            t["startedAt"] = None
            t["completedAt"] = None
        t["status"] = to
        note = args.note or ""
        if args.force:
            note = f"[forced] {note}"
        record(t, frm, to, note)
        save(root, board)
    print(json.dumps({"id": t["id"], "from": frm, "to": to, "releasedLeases": released}))


def cmd_set(args):
    root = find_root(args.root)
    with Lock(root):
        board = load(root)
        t = get(board, args.id)
        changed = {}
        for pair in args.pairs:
            if "=" not in pair:
                raise BoardError(f"expected key=value, got {pair!r}")
            k, v = pair.split("=", 1)
            if k not in SETTABLE:
                raise BoardError(f"{k} cannot be set this way. Settable: {', '.join(sorted(SETTABLE))}. "
                                 "Status changes go through 'move'; leases through 'lease'; the agent through 'agent'.")
            kind = SETTABLE[k]
            val = None if v in ("null", "") else v
            if kind is int:
                val = int(v)
            elif isinstance(kind, list) and val not in kind:
                raise BoardError(f"{k} must be one of: {', '.join(str(x) for x in kind)}")
            elif kind is str and k == "title" and not val:
                raise BoardError("title cannot be empty")
            t[k] = val
            changed[k] = val
        context = read_context(args)
        if context is not None:
            if not context.strip():
                raise BoardError("context cannot be empty")
            t["context"] = context
            changed["context"] = f"({len(context)} characters)"
        if not changed:
            raise BoardError("nothing to set")
        save(root, board)
        write_task_md(root, t)
    print(json.dumps({"id": t["id"], "set": changed}))


def cmd_agent(args):
    root = find_root(args.root)
    with Lock(root):
        board = load(root)
        t = get(board, args.id)
        if args.clear:
            t["agent"] = None
        else:
            if t["status"] not in ACTIVE:
                raise BoardError(f"{t['id']} is {t['status']}; move it to an active status before recording an agent")
            if not (args.name and args.pane and args.step):
                raise BoardError("--name, --pane and --step are required (or use --clear)")
            t["agent"] = {"name": args.name, "paneId": args.pane, "sessionId": args.session,
                          "step": args.step, "tier": args.tier, "startedAt": now()}
            t["workflowStep"] = args.step
        save(root, board)
    print(json.dumps({"id": t["id"], "agent": t["agent"]}))


def cmd_bump(args):
    root = find_root(args.root)
    key = {"retry": "retryCount", "yield": "yieldCount", "round": "executeRounds"}[args.counter]
    with Lock(root):
        board = load(root)
        t = get(board, args.id)
        t[key] = (t.get(key) or 0) + 1
        if args.reason:
            t["yieldReason"] = args.reason
        record(t, t["status"], t["status"], f"{key} -> {t[key]}" + (f": {args.reason}" if args.reason else ""))
        save(root, board)
    print(json.dumps({"id": t["id"], key: t[key]}))


def norm(path):
    p = path.strip()
    while p.startswith("./"):
        p = p[2:]
    return p


def cmd_lease(args):
    root = find_root(args.root)
    with Lock(root):
        board = load(root)
        t = get(board, args.id)
        if args.action == "release":
            released = t["leases"]["exclusive"] + t["leases"]["shared"]
            t["leases"] = {"exclusive": [], "shared": []}
            save(root, board)
            print(json.dumps({"id": t["id"], "released": released}))
            return

        if t["status"] not in ACTIVE:
            raise BoardError(f"{t['id']} is {t['status']}; leases can only be held by a task in an active status")
        f = root / t["docsPath"] / "declared-files.json"
        declared = {"exclusive": [], "shared": []}
        missing = not f.exists()
        if not missing:
            try:
                raw = json.loads(f.read_text())
            except json.JSONDecodeError as e:
                raise BoardError(f"{f} is not valid JSON: {e}")
            if not isinstance(raw, dict):
                raise BoardError(f"{f} must be an object with 'exclusive' and 'shared' lists")
            for k in ("exclusive", "shared"):
                vals = raw.get(k) or []
                if not isinstance(vals, list) or not all(isinstance(x, str) for x in vals):
                    raise BoardError(f"{f}: '{k}' must be a list of paths")
                declared[k] = sorted({norm(x) for x in vals})
            both = set(declared["exclusive"]) & set(declared["shared"])
            if both:
                declared["shared"] = [x for x in declared["shared"] if x not in both]

        conflicts = []
        for other in board["tasks"]:
            if other["id"] == t["id"]:
                continue
            oe = set(other["leases"]["exclusive"])
            osh = set(other["leases"]["shared"])
            for path in declared["exclusive"]:
                if path in oe:
                    conflicts.append({"file": path, "heldBy": other["id"], "theirLease": "exclusive"})
                elif path in osh:
                    conflicts.append({"file": path, "heldBy": other["id"], "theirLease": "shared"})
            for path in declared["shared"]:
                if path in oe:
                    conflicts.append({"file": path, "heldBy": other["id"], "theirLease": "exclusive"})
        if conflicts:
            print(json.dumps({"id": t["id"], "granted": False, "conflicts": conflicts}, indent=2))
            sys.exit(EXIT_LEASE_CONFLICT)

        t["declaredFiles"] = declared
        t["leases"] = {"exclusive": list(declared["exclusive"]), "shared": list(declared["shared"])}
        save(root, board)
    out = {"id": t["id"], "granted": True, "leases": t["leases"]}
    if missing:
        out["warning"] = "declared-files.json not found; granted with no leases"
    print(json.dumps(out, indent=2))


def cmd_leases(args):
    root = find_root(args.root)
    board = load(root)
    rows = []
    for t in board["tasks"]:
        for kind in ("exclusive", "shared"):
            for f in t["leases"][kind]:
                rows.append((f, kind, t["id"], t["status"]))
    if not rows:
        print("(no leases held)")
        return
    for f, kind, tid, status in sorted(rows):
        print(f"{kind.ljust(9)}  {tid.ljust(6)}  {status.ljust(10)}  {f}")


# ---------------------------------------------------------------------- cli

def build_parser():
    p = argparse.ArgumentParser(prog="board.py", description="Safe reads and writes of .formic/board.json")
    p.add_argument("--root", help="project root (default: nearest parent containing .formic/)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="create an empty board in this project")
    s.add_argument("--name")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("validate", help="check the board; exit 1 if invalid")
    s.set_defaults(fn=cmd_validate)

    s = sub.add_parser("migrate", help="convert a Formic server board to schemaVersion 2, keeping the original")
    s.set_defaults(fn=cmd_migrate)

    s = sub.add_parser("list", help="one summary per task")
    s.add_argument("--status", action="append", choices=STATUSES)
    s.add_argument("--active", action="store_true", help="only tasks in an active status")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("show", help="print one task in full")
    s.add_argument("id")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("add", help="create a task and its folder")
    s.add_argument("--title", required=True)
    s.add_argument("--context")
    s.add_argument("--context-file")
    s.add_argument("--type", choices=TYPES, default="standard")
    s.add_argument("--priority", choices=PRIORITIES, default="medium")
    s.add_argument("--tier", choices=TIERS)
    s.add_argument("--status", choices=["todo", "queued", "blocked"], default="todo")
    s.add_argument("--parent", help="goal task this is a child of")
    s.add_argument("--depends-on", help="comma-separated task ids")
    s.add_argument("--fix-for", help="task id this fixes")
    s.add_argument("--note")
    s.set_defaults(fn=cmd_add)

    s = sub.add_parser("move", help="change a task's status")
    s.add_argument("id")
    s.add_argument("status", choices=STATUSES)
    s.add_argument("--note")
    s.add_argument("--force", action="store_true", help="skip the transition check; needs --note")
    s.set_defaults(fn=cmd_move)

    s = sub.add_parser("set", help="set fields: key=value ...")
    s.add_argument("id")
    s.add_argument("pairs", nargs="*")
    s.add_argument("--context")
    s.add_argument("--context-file")
    s.set_defaults(fn=cmd_set)

    s = sub.add_parser("agent", help="record or clear the worker running a task's current step")
    s.add_argument("id")
    s.add_argument("--name")
    s.add_argument("--pane")
    s.add_argument("--session")
    s.add_argument("--step")
    s.add_argument("--tier", choices=TIERS)
    s.add_argument("--clear", action="store_true")
    s.set_defaults(fn=cmd_agent)

    s = sub.add_parser("bump", help="add 1 to a counter")
    s.add_argument("id")
    s.add_argument("counter", choices=["retry", "yield", "round"])
    s.add_argument("--reason")
    s.set_defaults(fn=cmd_bump)

    s = sub.add_parser("lease", help="acquire leases from declared-files.json, or release them")
    s.add_argument("id")
    s.add_argument("action", choices=["acquire", "release"])
    s.set_defaults(fn=cmd_lease)

    s = sub.add_parser("leases", help="list every lease held")
    s.set_defaults(fn=cmd_leases)
    return p


def main():
    args = build_parser().parse_args()
    try:
        args.fn(args)
    except BoardError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(EXIT_ERROR)


if __name__ == "__main__":
    main()
