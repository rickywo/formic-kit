"""Tests for the herdr plugin scripts: plugin/coordinator.sh, plugin/setup.sh, plugin/init.sh.

The coordinator tests use a stub herdr (HERDR_BIN_PATH) that records its arguments, so no
agent is started. The setup and init tests run the scripts with piped answers, a temporary
HOME and FORMIC_KIT_STATE_DIR, so the real install writes only into temporary folders.
"""
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugin"
SKILL_COUNT = len([d for d in (ROOT / "skills").iterdir() if d.is_dir()])

STUB_HERDR = """#!/bin/sh
echo "$*" >> "$STUB_LOG"
case "$1 $2" in
  "agent get") exit 1 ;;
  "pane split") echo '{"result": {"pane": {"pane_id": "p1"}}}'; exit 0 ;;
  "agent start")
    if [ "${STUB_START_FAIL:-}" = 1 ]; then
      echo "error: agent_not_ready: the agent is blocked" >&2
      exit 1
    fi
    echo "started"
    exit 0 ;;
  "integration status") echo "opencode: current"; echo "claude: current"; exit 0 ;;
esac
exit 0
"""


class PluginCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.home = self.tmp / "home"
        self.state = self.tmp / "state"
        self.project = self.tmp / "proj"
        self.stubs = self.tmp / "bin"
        self.log = self.tmp / "herdr.log"
        for d in (self.home, self.project, self.stubs):
            d.mkdir()
        (self.project / ".formic").mkdir()
        (self.project / ".formic" / "board.json").write_text("{}\n")
        herdr = self.stubs / "herdr"
        herdr.write_text(STUB_HERDR)
        herdr.chmod(herdr.stat().st_mode | stat.S_IXUSR)
        (self.stubs / "claude").write_text("#!/bin/sh\nexit 0\n")
        (self.stubs / "claude").chmod(0o755)
        for real in ("python3", "git"):
            found = shutil.which(real)
            self.assertIsNotNone(found, real + " is needed to run the tests")
            (self.stubs / real).symlink_to(found)

    def save_config(self, **values):
        self.state.mkdir(exist_ok=True)
        lines = ["%s=%s" % (k, v) for k, v in values.items()]
        lines.append("kit_dir=%s" % ROOT)  # so relink_if_moved has nothing to do
        (self.state / "config").write_text("\n".join(lines) + "\n")

    def env(self, **extra):
        env = {
            "HOME": str(self.home),
            "FORMIC_KIT_STATE_DIR": str(self.state),
            "PATH": str(self.stubs) + ":/usr/bin:/bin",
            "HERDR_BIN_PATH": str(self.stubs / "herdr"),
            "HERDR_PLUGIN_CONTEXT_JSON": json.dumps({"workspace_cwd": str(self.project)}),
            "HERDR_WORKSPACE_ID": "w1",
            "STUB_LOG": str(self.log),
        }
        env.update(extra)
        return env

    def run_script(self, name, stdin="", **extra):
        return subprocess.run(["bash", str(PLUGIN / name)], input=stdin, capture_output=True, text=True,
                              env=self.env(**extra), cwd=str(self.tmp))

    def logged(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def start_line(self):
        starts = [ln for ln in self.logged() if ln.startswith("agent start")]
        self.assertEqual(len(starts), 1, self.logged())
        return starts[0]

    def assert_no_keys_sent(self):
        for ln in self.logged():
            self.assertIn(" ".join(ln.split()[:2]), ("pane split", "agent get", "agent start"), ln)
            for word in ("send", "keys", "text", "send-text", "send-keys"):
                self.assertNotIn(word, ln.split()[:3], ln)


class TestCoordinator(PluginCase):
    OPENCODE_LINE = ("agent start coordinator-w1 --kind opencode --pane p1 --timeout 120000 "
                     "-- --agent formic-coordinator")

    def test_opencode_without_saved_settings_is_unchanged(self):
        r = self.run_script("coordinator.sh")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.start_line(), self.OPENCODE_LINE)
        self.assert_no_keys_sent()

    def test_opencode_with_saved_runtime_is_unchanged(self):
        self.save_config(runtime="opencode", claude_coordinator_model="ignored-id")
        r = self.run_script("coordinator.sh")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.start_line(), self.OPENCODE_LINE)
        self.assert_no_keys_sent()

    def test_claude_passes_saved_coordinator_model(self):
        self.save_config(runtime="claude", claude_coordinator_model="coord-id")
        r = self.run_script("coordinator.sh")
        self.assertEqual(r.returncode, 0, r.stderr)
        line = self.start_line()
        self.assertEqual(line, "agent start coordinator-w1 --kind claude --pane p1 --timeout 120000 "
                               "-- --agent formic-coordinator --model coord-id")
        words = line.split()
        self.assertEqual(words[words.index("--model") + 1], "coord-id")
        self.assertNotIn("--permission-mode", words)
        self.assertNotIn("--dangerously-skip-permissions", words)
        self.assert_no_keys_sent()

    def test_claude_without_coordinator_model_has_no_model_flag(self):
        self.save_config(runtime="claude", claude_sonnet_model="s", claude_haiku_model="h")
        r = self.run_script("coordinator.sh")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.start_line(), "agent start coordinator-w1 --kind claude --pane p1 "
                                            "--timeout 120000 -- --agent formic-coordinator")
        self.assert_no_keys_sent()

    def test_claude_start_failure_prints_guidance_and_sends_no_keys(self):
        self.save_config(runtime="claude", claude_coordinator_model="coord-id")
        r = self.run_script("coordinator.sh", STUB_START_FAIL="1")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("agent_not_ready", r.stderr)
        self.assertIn("Look at the new pane", r.stderr)
        self.assertIn("answer it there", r.stderr)
        self.assertIn("run this action again", r.stderr)
        self.assert_no_keys_sent()
        self.assertEqual([ln.split()[:2] for ln in self.logged()],
                         [["agent", "get"], ["pane", "split"], ["agent", "start"]])

    def test_unknown_runtime_stops_without_starting_anything(self):
        self.save_config(runtime="bogus")
        r = self.run_script("coordinator.sh")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unknown runtime", r.stderr)
        self.assertEqual([ln for ln in self.logged() if ln.startswith("agent start")], [])

    def test_existing_coordinator_is_focused_not_restarted(self):
        stub = self.stubs / "herdr"
        stub.write_text(STUB_HERDR.replace('"agent get") exit 1 ;;', '"agent get") exit 0 ;;'))
        self.save_config(runtime="claude", claude_coordinator_model="coord-id")
        r = self.run_script("coordinator.sh")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([ln.split()[:2] for ln in self.logged()], [["agent", "get"], ["agent", "focus"]])


class TestSetup(PluginCase):
    def state_values(self):
        out = {}
        for ln in (self.state / "config").read_text().splitlines():
            k, _, v = ln.partition("=")
            out[k] = v
        return out

    def test_setup_claude_passes_runtime_and_saves_ids(self):
        r = self.run_script("setup.sh", stdin="claude\ncoord-id\nsonnet-id\nhaiku-id\n\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        s = self.state_values()
        self.assertEqual(s["runtime"], "claude")
        self.assertEqual(s["claude_coordinator_model"], "coord-id")
        self.assertEqual(s["claude_sonnet_model"], "sonnet-id")
        self.assertEqual(s["claude_haiku_model"], "haiku-id")
        for name in ("worker-haiku", "worker-sonnet", "formic-coordinator"):
            self.assertTrue((self.home / ".claude" / "agents" / (name + ".md")).is_file(), name)
        self.assertEqual(len(list((self.home / ".claude" / "skills").iterdir())), SKILL_COUNT)
        self.assertIn("no provider prefix", r.stdout)
        self.assertFalse((self.home / ".config" / "opencode").exists())

    def test_runtime_question_comes_first(self):
        r = self.run_script("setup.sh", stdin="claude\nc\ns\nh\n\n")
        out = r.stdout + r.stderr
        self.assertLess(out.index("Runtime (opencode or claude)"), out.index("Coordinator model"))

    def test_setup_opencode_saves_opencode_ids(self):
        r = self.run_script("setup.sh", stdin="opencode\np/c\np/s\np/h\n\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        s = self.state_values()
        self.assertEqual(s["runtime"], "opencode")
        self.assertEqual(s["coordinator_model"], "p/c")
        self.assertEqual(s["sonnet_model"], "p/s")
        self.assertEqual(s["haiku_model"], "p/h")
        self.assertTrue((self.home / ".config" / "opencode" / "agents" / "worker-haiku.md").is_file())
        self.assertIn("provider/model form", r.stdout)
        self.assertFalse((self.home / ".claude").exists())

    def test_saved_runtime_is_the_default_answer(self):
        self.save_config(runtime="claude", claude_coordinator_model="old-c",
                         claude_sonnet_model="old-s", claude_haiku_model="old-h")
        r = self.run_script("setup.sh", stdin="\n\n\n\n\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        s = self.state_values()
        self.assertEqual(s["runtime"], "claude")
        self.assertEqual(s["claude_haiku_model"], "old-h")
        self.assertIn("Runtime (opencode or claude) [claude]", r.stderr)

    def test_invalid_runtime_three_times_stops(self):
        r = self.run_script("setup.sh", stdin="bogus\nbogus\nbogus\n\n")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("'bogus' is not a runtime", r.stdout)
        self.assertIn("Setup stopped", r.stdout)
        self.assertFalse((self.state / "config").exists())

    def test_invalid_runtime_then_valid_one_continues(self):
        r = self.run_script("setup.sh", stdin="bogus\nclaude\nc\ns\nh\n\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.state_values()["runtime"], "claude")


class TestInit(PluginCase):
    def test_init_text_and_claude_md_for_claude(self):
        self.save_config(runtime="claude")
        proj = self.tmp / "new"
        proj.mkdir()
        r = self.run_script("init.sh", stdin="y\n\n", FORMIC_PROJECT=str(proj))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("CLAUDE.md", r.stdout)
        self.assertEqual((proj / "CLAUDE.md").read_text(), "@AGENTS.md\n")

    def test_init_text_for_opencode_does_not_mention_claude_md(self):
        proj = self.tmp / "new"
        proj.mkdir()
        r = self.run_script("init.sh", stdin="y\n\n", FORMIC_PROJECT=str(proj))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("CLAUDE.md", r.stdout)
        self.assertFalse((proj / "CLAUDE.md").exists())
        self.assertTrue((proj / ".formic" / "board.json").is_file())


if __name__ == "__main__":
    unittest.main()
