#!/usr/bin/env python3
"""Live, read-only view of a formic-kit task board for a herdr plugin pane.

Usage: board_view.py <project-root>

Redraws when the board file changes. Keys: q or Esc to close, r to redraw.
Reads .formic/board.json directly and never writes it. Python 3.8+, standard library only.
"""

import json
import os
import select
import shutil
import sys
import termios
import time
import tty
from datetime import datetime, timezone

COLUMNS = [
    ("Queued", ["queued"]),
    ("Active", ["briefing", "planning", "declaring", "running", "verifying", "architecting"]),
    ("Blocked", ["blocked"]),
    ("Review", ["review"]),
    ("Todo", ["todo"]),
    ("Done", ["done"]),
]
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"
COLORS = {"Queued": "\033[36m", "Active": "\033[33m", "Blocked": "\033[31m",
          "Review": "\033[35m", "Todo": "\033[37m", "Done": "\033[32m"}


def age(iso):
    if not iso:
        return ""
    try:
        then = datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return ""
    secs = int((datetime.now(timezone.utc) - then).total_seconds())
    if secs < 90:
        return f"{max(secs, 0)}s"
    if secs < 5400:
        return f"{secs // 60}m"
    if secs < 129600:
        return f"{secs // 3600}h"
    return f"{secs // 86400}d"


def subtask_progress(root, task):
    try:
        with open(os.path.join(root, task["docsPath"], "subtasks.json")) as f:
            subs = json.load(f).get("subtasks", [])
    except (OSError, ValueError, KeyError):
        return ""
    if not subs:
        return ""
    done = sum(1 for s in subs if s.get("status") in ("completed", "skipped"))
    return f"{done}/{len(subs)} subtasks"


def task_lines(root, task, width):
    bits = [task.get("type", "?"), task.get("priority", "?")]
    if task.get("executeTier"):
        bits.append(task["executeTier"])
    status = task.get("status")
    if status not in ("queued", "todo", "blocked", "review", "done"):
        bits.insert(0, status)
        agent = task.get("agent") or {}
        if agent.get("name"):
            bits.append(f"agent {agent['name']} in {agent.get('paneId', '?')}")
        progress = subtask_progress(root, task)
        if progress:
            bits.append(progress)
    if task.get("retryCount"):
        bits.append(f"retries {task['retryCount']}")
    if status == "blocked" and task.get("dependsOn"):
        bits.append("waits for " + ", ".join(task["dependsOn"]))
    if status == "todo" and task.get("yieldReason"):
        bits.append("parked: " + task["yieldReason"])
    stamp = {"queued": "queuedAt", "review": "completedAt", "done": "completedAt"}.get(status, "startedAt")
    a = age(task.get(stamp))
    if a:
        bits.append(a + " ago")
    head = f"  {task['id']:<6} {task.get('title', '')}"
    detail = "         " + " · ".join(bits)
    return [head[:width], DIM + detail[:width] + RESET]


def render(root):
    width = shutil.get_terminal_size((100, 30)).columns
    path = os.path.join(root, ".formic", "board.json")
    out = []
    try:
        with open(path) as f:
            board = json.load(f)
    except (OSError, ValueError) as e:
        return [f"Cannot read {path}: {e}", "", "It may be mid-write; this view retries by itself."]
    tasks = board.get("tasks", [])
    name = (board.get("meta") or {}).get("projectName", os.path.basename(root))
    counts = []
    for title, statuses in COLUMNS:
        n = sum(1 for t in tasks if t.get("status") in statuses)
        counts.append(f"{title.lower()} {n}")
    out.append(f"{BOLD}{name}{RESET}  {DIM}{root}{RESET}")
    out.append(DIM + "  ".join(counts) + RESET)
    for title, statuses in COLUMNS:
        group = [t for t in tasks if t.get("status") in statuses]
        if not group:
            continue
        if title == "Queued":
            group.sort(key=lambda t: (0 if t.get("fixForTaskId") else 1,
                                      PRIORITY_ORDER.get(t.get("priority"), 9), t.get("queuedAt") or ""))
        out.append("")
        out.append(f"{COLORS[title]}{BOLD}{title} ({len(group)}){RESET}")
        limit = 5 if title == "Done" else len(group)
        for t in group[-limit:] if title == "Done" else group:
            out.extend(task_lines(root, t, width))
        if title == "Done" and len(group) > limit:
            out.append(DIM + f"  ... and {len(group) - limit} older" + RESET)
    return out


def draw(root):
    rows = shutil.get_terminal_size((100, 30)).lines
    lines = render(root)
    footer = DIM + "read-only · updates when the board changes · q to close" + RESET
    body = lines[: max(rows - 2, 1)]
    if len(lines) > len(body):
        body[-1] = DIM + f"  ... {len(lines) - len(body) + 1} more lines; enlarge the pane" + RESET
    sys.stdout.write("\033[H\033[2J" + "\r\n".join(body) + "\r\n\r\n" + footer)
    sys.stdout.flush()


def main():
    if len(sys.argv) != 2:
        print("usage: board_view.py <project-root>", file=sys.stderr)
        return 2
    root = os.path.abspath(sys.argv[1])
    path = os.path.join(root, ".formic", "board.json")
    interactive = sys.stdin.isatty()
    old = termios.tcgetattr(sys.stdin) if interactive else None
    try:
        if interactive:
            tty.setcbreak(sys.stdin.fileno())
            sys.stdout.write("\033[?25l")
        last = None
        tick = 0
        while True:
            try:
                stamp = os.stat(path).st_mtime_ns
            except OSError:
                stamp = None
            size = shutil.get_terminal_size((100, 30))
            key = (stamp, size, tick // 30)  # also redraw every 30s so the ages move
            if key != last:
                draw(root)
                last = key
            if not interactive:
                print()
                return 0
            ready, _, _ = select.select([sys.stdin], [], [], 1.0)
            if ready:
                ch = sys.stdin.read(1)
                if ch in ("q", "Q", "\x1b", "\x03", ""):
                    return 0
                if ch in ("r", "R"):
                    last = None
            tick += 1
    except KeyboardInterrupt:
        return 0
    finally:
        if interactive:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)
            sys.stdout.write("\033[?25h\033[0m\r\n")
            sys.stdout.flush()


if __name__ == "__main__":
    sys.exit(main())
