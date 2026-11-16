#!/usr/bin/env python3
"""Tests for skills/formic-dispatch/scripts/async_brief.sh. Run: python3 -m unittest discover -s tests"""

import os
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "formic-dispatch" / "scripts" / "async_brief.sh"

# Stub send_brief.sh: prints a line of JSON, then exits with the code in `code`, after
# sleeping for the number of seconds in `delay`. Both are files next to it.
STUB = r"""#!/bin/bash
here="$(dirname "$0")"
echo "$*" >> "$here/calls.log"
echo $$ > "$here/stub.pid"
sleep "$(cat "$here/delay")"
echo '{"delivered": true, "status": "idle"}'
echo "stub stderr line" >&2
exit "$(cat "$here/code")"
"""


class AsyncBriefCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.scripts = self.dir / "scripts"
        self.scripts.mkdir()
        shutil.copy(SCRIPT, self.scripts / "async_brief.sh")
        (self.scripts / "send_brief.sh").write_text(STUB)
        self.set_stub(delay=0, code=0)
        self.brief = self.dir / "brief.md"
        self.brief.write_text("brief\n")
        self.result = self.dir / "output" / "result-plan.json"

    def tearDown(self):
        for path in (self.scripts / "stub.pid", Path(str(self.result) + ".pid")):
            if path.exists():
                try:
                    os.kill(int(path.read_text().strip()), signal.SIGKILL)
                except (OSError, ValueError):
                    pass
        self.tmp.cleanup()

    def set_stub(self, delay, code):
        (self.scripts / "delay").write_text(str(delay))
        (self.scripts / "code").write_text(str(code))

    def run_async(self, *args, poll="1", timeout=60):
        env = dict(os.environ, FORMIC_ASYNC_POLL_SECONDS=poll)
        started = time.time()
        r = subprocess.run(["bash", str(self.scripts / "async_brief.sh"), *args],
                           capture_output=True, text=True, timeout=timeout, env=env)
        self.elapsed = time.time() - started
        return r

    def start(self, name="t12-plan", timeout_ms="1800000"):
        return self.run_async("start", name, str(self.brief), timeout_ms, str(self.result))

    def wait(self, seconds=None, poll="1"):
        args = ["wait", str(self.result)] + ([str(seconds)] if seconds is not None else [])
        return self.run_async(*args, poll=poll)

    def part(self, suffix):
        return Path(str(self.result) + suffix)


class StartTests(AsyncBriefCase):
    def test_start_returns_at_once_and_prints_started(self):
        self.set_stub(delay=5, code=0)
        r = self.start()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "started")
        self.assertLess(self.elapsed, 3)
        self.assertTrue(self.part(".pid").exists())
        self.assertFalse(self.part(".code").exists())

    def test_start_passes_its_arguments_to_send_brief(self):
        self.start(name="t12-plan", timeout_ms="900000")
        self.wait(10)
        calls = (self.scripts / "calls.log").read_text().splitlines()
        self.assertEqual(calls, [f"t12-plan {self.brief} 900000"])

    def test_start_refuses_while_a_run_is_alive(self):
        self.set_stub(delay=20, code=0)
        self.assertEqual(self.start().returncode, 0)
        r = self.start()
        self.assertEqual(r.returncode, 1)
        self.assertIn("still going", r.stderr)
        self.assertEqual(len((self.scripts / "calls.log").read_text().splitlines()), 1)

    def test_start_again_after_the_run_finished(self):
        self.assertEqual(self.start().returncode, 0)
        self.assertEqual(self.wait(10).returncode, 0)
        self.assertEqual(self.start().returncode, 0)
        self.assertEqual(self.wait(10).returncode, 0)
        self.assertEqual(len((self.scripts / "calls.log").read_text().splitlines()), 2)

    def test_start_usage_errors(self):
        for args in (["start"], ["start", "a", str(self.brief), "1000"],
                     ["start", "a", str(self.dir / "missing.md"), "1000", str(self.result)], []):
            with self.subTest(args=args):
                r = self.run_async(*args)
                self.assertEqual(r.returncode, 1)
                self.assertIn("usage", r.stderr)


class WaitTests(AsyncBriefCase):
    def test_wait_prints_the_final_json_and_exit_code(self):
        self.set_stub(delay=0, code=0)
        self.start()
        r = self.wait(10)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), '{"delivered": true, "status": "idle"}')

    def test_wait_passes_on_the_exit_code_of_send_brief(self):
        for code in (3, 1):
            with self.subTest(code=code):
                self.set_stub(delay=0, code=code)
                self.start()
                r = self.wait(10)
                self.assertEqual(r.returncode, code)
                self.assertTrue(r.stdout.startswith("{"))

    def test_wait_prints_still_running_and_exits_zero(self):
        self.set_stub(delay=15, code=3)
        self.start()
        r = self.wait(2)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "still running")
        self.assertGreaterEqual(self.elapsed, 1.5)
        self.assertLess(self.elapsed, 10)

    def test_second_wait_returns_the_result_after_the_run_finished(self):
        self.set_stub(delay=3, code=3)
        self.start()
        first = self.wait(1)
        self.assertEqual(first.stdout.strip(), "still running")
        second = self.wait(10)
        self.assertEqual(second.returncode, 3)
        self.assertTrue(second.stdout.startswith("{"))
        third = self.wait(1)
        self.assertEqual(third.returncode, 3)
        self.assertEqual(third.stdout, second.stdout)

    def test_stderr_goes_to_the_err_file(self):
        self.start()
        self.wait(10)
        self.assertEqual(self.part(".err").read_text().strip(), "stub stderr line")
        self.assertFalse(self.part(".part").exists())
        self.assertEqual(self.part(".code").read_text().strip(), "0")

    def test_default_wait_is_480_and_it_is_capped_at_540(self):
        text = SCRIPT.read_text()
        self.assertIn('seconds="${2:-480}"', text)
        self.assertIn("MAX_WAIT=540", text)

    def test_seconds_above_540_are_capped(self):
        # With a poll of 100 s the loop checks at 0, 100, ... so a cap of 540 gives
        # 6 polls (600 s) at most. Use a stub sleep to keep the test fast.
        stub_bin = self.dir / "bin"
        stub_bin.mkdir()
        (stub_bin / "sleep").write_text("#!/bin/bash\necho \"$1\" >> \"$(dirname \"$0\")/sleeps.log\"\n")
        (stub_bin / "sleep").chmod(0o755)
        self.set_stub(delay=30, code=0)
        self.start()
        env = dict(os.environ, FORMIC_ASYNC_POLL_SECONDS="100",
                   PATH=f"{stub_bin}{os.pathsep}{os.environ['PATH']}")
        r = subprocess.run(["bash", str(self.scripts / "async_brief.sh"), "wait", str(self.result), "99999"],
                           capture_output=True, text=True, timeout=60, env=env)
        self.assertEqual(r.stdout.strip(), "still running")
        sleeps = (stub_bin / "sleeps.log").read_text().split()
        self.assertEqual(sum(int(x) for x in sleeps), 600)  # ceil(540/100) polls of 100 s
        self.assertEqual(len(sleeps), 6)

    def test_bad_seconds_is_a_usage_error(self):
        self.start()
        r = self.wait("abc")
        self.assertEqual(r.returncode, 1)
        self.assertIn("usage", r.stderr)

    def test_wait_without_a_started_run(self):
        r = self.wait(1)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no run was started", r.stderr)

    def test_a_killed_wrapper_gives_the_stopped_without_a_result_json(self):
        self.set_stub(delay=30, code=0)
        self.start()
        time.sleep(0.5)
        pid = int(self.part(".pid").read_text().strip())
        os.kill(pid, signal.SIGKILL)
        time.sleep(0.5)
        r = self.wait(10)
        self.assertEqual(r.returncode, 1)
        self.assertIn('"delivered": false', r.stdout)
        self.assertIn("stopped without a result", r.stdout)
        self.assertLess(self.elapsed, 8)


if __name__ == "__main__":
    unittest.main()
