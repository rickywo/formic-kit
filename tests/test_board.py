#!/usr/bin/env python3
"""Tests for skills/formic-board/scripts/board.py. Run: python3 tests/test_board.py"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BOARD = Path(__file__).resolve().parent.parent / "skills" / "formic-board" / "scripts" / "board.py"


class BoardCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_board(self, *args, ok=True):
        r = subprocess.run([sys.executable, str(BOARD), "--root", str(self.root), *args],
                           capture_output=True, text=True)
        if ok:
            self.assertEqual(r.returncode, 0, f"{args}: {r.stderr}{r.stdout}")
        return r

    def out(self, *args):
        return json.loads(self.run_board(*args).stdout)

    def board(self):
        return json.loads((self.root / ".formic" / "board.json").read_text())

    def task(self, tid):
        return next(t for t in self.board()["tasks"] if t["id"] == tid)

    def add(self, title="Add a thing", *extra):
        return self.out("add", "--title", title, "--context", "Do the thing.", *extra)["id"]

    def declare(self, tid, exclusive=(), shared=()):
        d = self.root / self.task(tid)["docsPath"]
        (d / "declared-files.json").write_text(json.dumps({"exclusive": list(exclusive), "shared": list(shared)}))

    def to_running(self, tid):
        for s in ("queued", "briefing", "planning", "declaring"):
            self.run_board("move", tid, s)


class TestBasics(BoardCase):
    def test_init_add_validate(self):
        self.run_board("init", "--name", "demo")
        self.assertIn("already exists", self.run_board("init", ok=False).stderr)
        tid = self.add("Fix: the Login page!! (urgent)")
        self.assertEqual(tid, "t-1")
        t = self.task(tid)
        self.assertEqual(t["docsPath"], ".formic/tasks/t-1_fix-the-login-page-urgent")
        self.assertEqual(t["status"], "todo")
        md = (self.root / t["docsPath"] / "TASK.md").read_text()
        self.assertIn("Do the thing.", md)
        self.assertTrue((self.root / t["docsPath"] / "output").is_dir())
        self.assertIn("OK: 1 tasks", self.run_board("validate").stdout)
        cut = self.add("Add export button to the boar header")
        self.assertEqual(self.task(cut)["docsPath"], ".formic/tasks/t-2_add-export-button-to-the-boar")
        self.assertTrue((self.root / ".formic" / "board.json.backup").exists())

    def test_ids_never_reused(self):
        self.run_board("init")
        self.add()
        self.add()
        b = self.board()
        b["tasks"] = [t for t in b["tasks"] if t["id"] != "t-2"]
        (self.root / ".formic" / "board.json").write_text(json.dumps(b))
        self.assertEqual(self.add(), "t-3")

    def test_add_requires_context(self):
        self.run_board("init")
        r = self.run_board("add", "--title", "x", ok=False)
        self.assertNotEqual(r.returncode, 0)

    def test_set_and_task_md_refresh(self):
        self.run_board("init")
        tid = self.add()
        self.run_board("set", tid, "executeTier=haiku", "priority=high")
        t = self.task(tid)
        self.assertEqual((t["executeTier"], t["priority"]), ("haiku", "high"))
        self.assertIn("Execute tier: haiku", (self.root / t["docsPath"] / "TASK.md").read_text())
        self.assertNotEqual(self.run_board("set", tid, "status=done", ok=False).returncode, 0)
        self.assertNotEqual(self.run_board("set", tid, "executeTier=opus", ok=False).returncode, 0)


class TestTransitions(BoardCase):
    def test_happy_path_standard(self):
        self.run_board("init")
        tid = self.add()
        for s in ("queued", "briefing", "planning", "declaring", "running", "verifying", "review", "done"):
            self.run_board("move", tid, s)
        t = self.task(tid)
        self.assertEqual(t["status"], "done")
        self.assertIsNotNone(t["startedAt"])
        self.assertIsNotNone(t["completedAt"])
        self.assertEqual(len(t["history"]), 9)

    def test_gate_cannot_be_skipped(self):
        self.run_board("init")
        tid = self.add()
        self.to_running(tid)
        self.run_board("move", tid, "running")
        r = self.run_board("move", tid, "review", ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("not an allowed transition", r.stderr)
        self.assertEqual(self.task(tid)["status"], "running")

    def test_force_needs_note(self):
        self.run_board("init")
        tid = self.add()
        self.assertNotEqual(self.run_board("move", tid, "review", "--force", ok=False).returncode, 0)
        self.run_board("move", tid, "review", "--force", "--note", "repair")
        self.assertIn("[forced]", self.task(tid)["history"][-1]["note"])

    def test_any_status_can_park_to_todo_and_requeue_resets_counters(self):
        self.run_board("init")
        tid = self.add()
        self.to_running(tid)
        self.run_board("bump", tid, "retry", "--reason", "plan step failed")
        self.assertEqual(self.task(tid)["retryCount"], 1)
        self.run_board("move", tid, "todo", "--note", "parked")
        self.assertIsNone(self.task(tid)["startedAt"])
        self.run_board("move", tid, "queued")
        t = self.task(tid)
        self.assertEqual((t["retryCount"], t["yieldReason"]), (0, None))

    def test_retry_requeue_keeps_counters(self):
        self.run_board("init")
        tid = self.add()
        self.run_board("move", tid, "queued")
        self.run_board("move", tid, "briefing")
        self.run_board("bump", tid, "retry")
        self.run_board("move", tid, "queued", "--note", "brief failed")
        self.assertEqual(self.task(tid)["retryCount"], 1)


class TestDependencies(BoardCase):
    def test_blocked_child_cannot_queue_until_dependency_in_review(self):
        self.run_board("init")
        goal = self.add("Build the feature", "--type", "goal")
        a = self.add("Add schema", "--parent", goal, "--status", "queued")
        r = self.run_board("add", "--title", "Add API", "--context", "x", "--parent", goal, "--depends-on", a, ok=False)
        self.assertIn("--status blocked", r.stderr)
        b = self.add("Add API", "--parent", goal, "--depends-on", a, "--status", "blocked")
        self.assertEqual(self.task(goal)["childTaskIds"], [a, b])
        r = self.run_board("move", b, "queued", ok=False)
        self.assertIn("still depends on", r.stderr)
        for s in ("briefing", "planning", "declaring", "running", "verifying", "review"):
            self.run_board("move", a, s)
        self.run_board("move", b, "queued")
        self.assertIn(f"deps=[{a}(review)]", self.run_board("list").stdout)

    def test_unknown_dependency_rejected(self):
        self.run_board("init")
        r = self.run_board("add", "--title", "x", "--context", "x", "--depends-on", "t-99", "--status", "blocked", ok=False)
        self.assertIn("no such task", r.stderr)


class TestLeases(BoardCase):
    def two_declaring(self):
        self.run_board("init")
        a, b = self.add("Task A"), self.add("Task B")
        self.to_running(a)
        self.to_running(b)
        return a, b

    def test_exclusive_conflict_blocks_second_task(self):
        a, b = self.two_declaring()
        self.declare(a, exclusive=["./src/a.ts"], shared=["package.json"])
        self.declare(b, exclusive=["src/a.ts", "src/b.ts"])
        self.assertTrue(self.out("lease", a, "acquire")["granted"])
        r = self.run_board("lease", b, "acquire", ok=False)
        self.assertEqual(r.returncode, 3)
        res = json.loads(r.stdout)
        self.assertFalse(res["granted"])
        self.assertEqual(res["conflicts"], [{"file": "src/a.ts", "heldBy": a, "theirLease": "exclusive"}])
        self.assertEqual(self.task(b)["leases"], {"exclusive": [], "shared": []})

    def test_shared_with_shared_ok_shared_vs_exclusive_not(self):
        a, b = self.two_declaring()
        self.declare(a, shared=["package.json"])
        self.declare(b, shared=["package.json"])
        self.out("lease", a, "acquire")
        self.assertTrue(self.out("lease", b, "acquire")["granted"])
        self.out("lease", b, "release")
        self.declare(b, exclusive=["package.json"])
        self.assertEqual(self.run_board("lease", b, "acquire", ok=False).returncode, 3)

    def test_leaving_active_releases_leases_and_agent(self):
        a, b = self.two_declaring()
        self.declare(a, exclusive=["src/a.ts"])
        self.declare(b, exclusive=["src/a.ts"])
        self.out("lease", a, "acquire")
        self.run_board("agent", a, "--name", "t1-execute", "--pane", "w1:p2", "--step", "execute", "--tier", "haiku")
        self.run_board("move", a, "running")
        self.assertEqual(self.task(a)["leases"]["exclusive"], ["src/a.ts"])
        self.run_board("move", a, "verifying")
        res = self.out("move", a, "review")
        self.assertEqual(res["releasedLeases"], ["src/a.ts"])
        self.assertIsNone(self.task(a)["agent"])
        self.assertTrue(self.out("lease", b, "acquire")["granted"])

    def test_missing_declared_files_grants_nothing_with_warning(self):
        a, _ = self.two_declaring()
        self.assertIn("warning", self.out("lease", a, "acquire"))

    def test_lease_needs_active_status(self):
        self.run_board("init")
        a = self.add()
        self.assertNotEqual(self.run_board("lease", a, "acquire", ok=False).returncode, 0)


class TestIntegrity(BoardCase):
    def test_invalid_board_is_never_written(self):
        self.run_board("init")
        a = self.add()
        p = self.root / ".formic" / "board.json"
        b = self.board()
        b["tasks"][0]["leases"] = {"exclusive": ["x"], "shared": []}
        p.write_text(json.dumps(b))
        before = p.read_text()
        r = self.run_board("set", a, "priority=low", ok=False)
        self.assertIn("refusing to write", r.stderr)
        self.assertEqual(p.read_text(), before)
        self.assertEqual(self.run_board("validate", ok=False).returncode, 1)

    def test_corrupt_json_reports_backup(self):
        self.run_board("init")
        (self.root / ".formic" / "board.json").write_text("{not json")
        self.assertIn("board.json.backup", self.run_board("list", ok=False).stderr)


class TestMigrate(BoardCase):
    def test_v1_board(self):
        d = self.root / ".formic"
        (d / "tasks" / "t-3_old-task").mkdir(parents=True)
        v1 = {"meta": {"projectName": "Formic", "repoPath": "/x", "createdAt": "2026-07-10T05:36:34.197Z", "nextTaskId": 2},
              "tasks": [
                  {"id": "t-3", "title": "Old task", "context": "ctx", "priority": "medium", "status": "running",
                   "docsPath": ".formic/tasks/t-3_old-task", "agentLogs": ["x"], "pid": 12, "type": "quick",
                   "workflowLogs": {}, "retryCount": None, "recoveryCount": 4, "dependsOn": ["sym"],
                   "dependsOnResolved": [], "declaredFiles": {"exclusive": ["a"], "shared": []}},
                  {"id": "t-bootstrap", "title": "Setup", "context": "c", "priority": "high", "status": "review",
                   "docsPath": ".formic/tasks/t-bootstrap_setup-guidelines", "agentLogs": [], "pid": None}]}
        (d / "board.json").write_text(json.dumps(v1))
        self.assertIn("migrate", self.run_board("list", ok=False).stderr)
        out = self.run_board("migrate").stdout
        self.assertIn("now queued: t-3", out)
        self.assertEqual(len(list(d.glob("board.json.v1-*"))), 1)
        b = self.board()
        self.assertEqual(b["meta"]["nextTaskId"], 4)
        self.assertNotIn("repoPath", b["meta"])
        t = self.task("t-3")
        self.assertEqual((t["status"], t["retryCount"], t["dependsOn"]), ("queued", 0, []))
        for k in ("agentLogs", "pid", "workflowLogs", "recoveryCount"):
            self.assertNotIn(k, t)
        self.assertEqual(self.task("t-bootstrap")["type"], "standard")
        self.run_board("validate")
        self.assertIn("nothing to do", self.run_board("migrate").stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
