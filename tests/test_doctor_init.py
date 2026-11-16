"""Tests for install.sh doctor and install.sh init, which follow the configured runtime.

Every test runs install.sh with a temporary HOME, FORMIC_KIT_STATE_DIR, config folders and a
PATH that holds only stub programs (claude, herdr, optionally opencode) plus python3 and git.
Nothing touches the real ~/.config/opencode, ~/.claude or ~/.config/formic-kit, and no real
Claude Code or opencode session is started.
"""
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "install.sh"
SKILL_COUNT = len([d for d in (ROOT / "skills").iterdir() if d.is_dir()])

STUB_CLAUDE = "#!/bin/sh\nexit 0\n"
STUB_HERDR = """#!/bin/sh
if [ "$1" = integration ] && [ "$2" = status ]; then
  echo "opencode: current"
  echo "claude: current"
  exit 0
fi
exit 0
"""
STUB_OPENCODE = """#!/bin/sh
if [ "$1" = agent ] && [ "$2" = list ]; then
  echo "worker-haiku (subagent)"
  echo "worker-sonnet (subagent)"
  echo "formic-coordinator (primary)"
fi
exit 0
"""


def snapshot(*dirs):
    """Map each path under the given dirs to its content, or 'link:<target>' for a link."""
    out = {}
    for base in dirs:
        for p in sorted(Path(base).rglob("*")):
            if p.is_symlink():
                out[str(p)] = "link:" + os.readlink(p)
            elif p.is_file():
                out[str(p)] = p.read_text()
    return out


class DoctorInitCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.home = self.tmp / "home"
        self.state = self.tmp / "state"
        self.cfg = self.tmp / "cfg-a"
        self.cl = self.tmp / "cfg-b"
        self.project = self.tmp / "proj"
        self.stubs = self.tmp / "bin"
        for d in (self.home, self.project, self.stubs):
            d.mkdir()
        self.add_stub("claude", STUB_CLAUDE)
        self.add_stub("herdr", STUB_HERDR)
        for real in ("python3", "git"):
            found = shutil.which(real)
            self.assertIsNotNone(found, real + " is needed to run the tests")
            (self.stubs / real).symlink_to(found)

    def add_stub(self, name, body):
        p = self.stubs / name
        p.write_text(body)
        p.chmod(p.stat().st_mode | stat.S_IXUSR)

    def run_install(self, *args, cwd=None):
        env = {
            "HOME": str(self.home),
            "FORMIC_KIT_STATE_DIR": str(self.state),
            "PATH": str(self.stubs) + ":/usr/bin:/bin",
        }
        cmd = ["bash", str(INSTALL), *args, "--config-dir", str(self.cfg), "--claude-dir", str(self.cl)]
        return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(cwd or self.tmp))

    def claude_install(self, *extra):
        r = self.run_install("--runtime", "claude", "--coordinator-model", "coord-id",
                             "--sonnet-model", "sonnet-id", "--haiku-model", "haiku-id", *extra)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def opencode_install(self):
        r = self.run_install("--coordinator-model", "p/coord", "--sonnet-model", "p/sonnet",
                             "--haiku-model", "p/haiku")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def make_project(self, *init_args):
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        r = self.run_install("init", str(self.project), *init_args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def doctor(self, *args):
        return self.run_install("doctor", *args)


class TestClaudeDoctor(DoctorInitCase):
    def test_passing_claude_doctor(self):
        self.claude_install()
        self.make_project()
        r = self.doctor(str(self.project))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("  ok    claude found", r.stdout)
        self.assertIn("  ok    herdr claude integration: current", r.stdout)
        self.assertIn("  ok    %d of %d kit skills are reachable" % (SKILL_COUNT, SKILL_COUNT), r.stdout)
        self.assertIn("  ok    worker-haiku", r.stdout)
        self.assertIn("  ok    worker-sonnet", r.stdout)
        self.assertIn("  ok    formic-coordinator", r.stdout)
        self.assertIn("  ok    claude haiku model: haiku-id", r.stdout)
        self.assertIn("  ok    CLAUDE.md imports AGENTS.md", r.stdout)
        self.assertIn("All required checks passed.", r.stdout)
        self.assertNotIn("opencode", r.stdout.lower())

    def test_claude_runtime_from_flag_without_saved_state(self):
        r = self.doctor("--runtime", "claude")
        self.assertEqual(r.returncode, 1)
        self.assertIn("  ok    claude found", r.stdout)
        self.assertIn("FAIL  claude haiku model id is not saved", r.stdout)

    def test_claude_not_required_tool_is_opencode(self):
        self.claude_install()
        (self.stubs / "claude").unlink()
        r = self.doctor()
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL  claude is not installed or not on PATH", r.stdout)
        self.assertNotIn("opencode is not installed", r.stdout)

    def test_missing_worker_agent_fails(self):
        self.claude_install()
        (self.cl / "agents" / "worker-haiku.md").unlink()
        r = self.doctor()
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL  agent worker-haiku not found", r.stdout)
        self.assertIn("  ok    worker-sonnet", r.stdout)

    def test_missing_worker_model_id_fails(self):
        r = self.run_install("--runtime", "claude", "--sonnet-model", "sonnet-id")
        self.assertEqual(r.returncode, 1)  # install itself reports the missing haiku id
        d = self.doctor()
        self.assertEqual(d.returncode, 1)
        self.assertIn("FAIL  claude haiku model id is not saved", d.stdout)
        self.assertIn("  ok    claude sonnet model: sonnet-id", d.stdout)

    def test_missing_coordinator_model_is_only_a_note(self):
        r = self.run_install("--runtime", "claude", "--sonnet-model", "sonnet-id", "--haiku-model", "haiku-id")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        d = self.doctor()
        self.assertEqual(d.returncode, 0, d.stdout)
        self.assertIn("  note  no claude coordinator model id saved", d.stdout)

    def test_missing_coordinator_agent_is_only_a_note(self):
        self.claude_install()
        (self.cl / "agents" / "formic-coordinator.md").unlink()
        d = self.doctor()
        self.assertEqual(d.returncode, 0, d.stdout)
        self.assertIn("  note  formic-coordinator agent not installed (optional)", d.stdout)

    def test_agent_file_without_marker_gets_a_note(self):
        self.claude_install()
        (self.cl / "agents" / "worker-sonnet.md").write_text("---\nname: worker-sonnet\n---\nmine\n")
        d = self.doctor()
        self.assertEqual(d.returncode, 0, d.stdout)
        self.assertIn("note  worker-sonnet is your own agent file, not the kit's", d.stdout)

    def test_broken_skill_link_is_detected(self):
        self.claude_install()
        victim = self.cl / "skills" / "formic-board"
        victim.unlink()
        victim.symlink_to(self.tmp / "gone")
        d = self.doctor()
        self.assertEqual(d.returncode, 1)
        self.assertIn("FAIL  broken link %s" % victim, d.stdout)
        self.assertIn("note  broken links usually mean", d.stdout)

    def test_missing_claude_integration_fails(self):
        self.claude_install()
        self.add_stub("herdr", '#!/bin/sh\n[ "$1" = integration ] && echo "opencode: current"\nexit 0\n')
        d = self.doctor()
        self.assertEqual(d.returncode, 1)
        self.assertIn("FAIL  herdr claude integration status unknown; run: herdr integration install claude",
                      d.stdout)

    def test_project_claude_md_notes(self):
        self.claude_install()
        self.make_project()
        claude_md = self.project / "CLAUDE.md"
        claude_md.write_text("my own notes\n")
        d = self.doctor(str(self.project))
        self.assertEqual(d.returncode, 0, d.stdout)
        self.assertIn("note  CLAUDE.md exists but does not import AGENTS.md", d.stdout)
        claude_md.unlink()
        d = self.doctor(str(self.project))
        self.assertEqual(d.returncode, 0, d.stdout)
        self.assertIn("note  no CLAUDE.md; Claude Code will not read AGENTS.md", d.stdout)

    def test_skills_reachable_from_project_claude_folder(self):
        self.claude_install()
        shutil.rmtree(self.cl / "skills")
        self.make_project("--local-skills")
        d = self.doctor(str(self.project))
        self.assertEqual(d.returncode, 0, d.stdout)
        self.assertIn("  ok    %d of %d kit skills are reachable" % (SKILL_COUNT, SKILL_COUNT), d.stdout)


class TestOpencodeDoctor(DoctorInitCase):
    def setUp(self):
        super().setUp()
        self.add_stub("opencode", STUB_OPENCODE)

    def check_opencode_lines(self, out):
        self.assertIn("  ok    opencode found", out)
        self.assertIn("  ok    herdr opencode integration: current", out)
        self.assertIn("  ok    %d of %d kit skills are reachable" % (SKILL_COUNT, SKILL_COUNT), out)
        self.assertIn("  ok    worker-haiku (p/haiku)", out)
        self.assertIn("  ok    worker-sonnet (p/sonnet)", out)
        self.assertIn("  ok    formic-coordinator", out)
        self.assertNotIn("Models", out)
        self.assertNotIn("claude", out.lower())
        self.assertNotIn("CLAUDE.md", out)

    def test_opencode_doctor_lines_are_unchanged(self):
        self.opencode_install()
        self.make_project()
        r = self.doctor(str(self.project))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.check_opencode_lines(r.stdout)
        self.assertIn("All required checks passed.", r.stdout)

    def test_doctor_without_saved_runtime_behaves_as_opencode(self):
        self.opencode_install()
        state = self.state / "config"
        state.write_text("".join(ln + "\n" for ln in state.read_text().splitlines()
                                 if not ln.startswith("runtime=")))
        self.assertNotIn("runtime=", state.read_text())
        r = self.doctor()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.check_opencode_lines(r.stdout)

    def test_opencode_doctor_does_not_need_claude(self):
        self.opencode_install()
        (self.stubs / "claude").unlink()
        r = self.doctor()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("claude", r.stdout.lower())

    def test_opencode_is_required_for_opencode_runtime(self):
        self.opencode_install()
        (self.stubs / "opencode").unlink()
        r = self.doctor()
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL  opencode is not installed or not on PATH", r.stdout)


class TestInit(DoctorInitCase):
    def test_claude_init_creates_claude_md_once(self):
        self.claude_install()
        r = self.run_install("init", str(self.project))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.project / "CLAUDE.md").read_text(), "@AGENTS.md\n")
        self.assertIn("CLAUDE.md: created with @AGENTS.md", r.stdout)
        self.assertIn("start Claude Code inside herdr", r.stdout)
        before = snapshot(self.project)
        r2 = self.run_install("init", str(self.project))
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertEqual(snapshot(self.project), before)
        self.assertIn("CLAUDE.md: already exists, left as it is", r2.stdout)

    def test_claude_init_with_runtime_flag_only(self):
        r = self.run_install("init", str(self.project), "--runtime", "claude")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.project / "CLAUDE.md").read_text(), "@AGENTS.md\n")

    def test_existing_claude_md_is_untouched(self):
        self.claude_install()
        (self.project / "CLAUDE.md").write_text("# my notes\nkeep me\n")
        r = self.run_install("init", str(self.project))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.project / "CLAUDE.md").read_text(), "# my notes\nkeep me\n")
        self.assertIn("CLAUDE.md: already exists, left as it is", r.stdout)
        self.assertNotIn("created with", r.stdout)

    def test_opencode_init_does_not_touch_claude_files(self):
        self.opencode_install()
        r = self.run_install("init", str(self.project))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.project / "CLAUDE.md").exists())
        self.assertFalse((self.project / ".claude").exists())
        self.assertNotIn("CLAUDE", r.stdout)
        self.assertIn("start opencode inside herdr", r.stdout)
        self.assertIn("The first opencode start in a new project takes about a minute.", r.stdout)

    def test_init_without_any_settings_behaves_as_opencode(self):
        r = self.run_install("init", str(self.project))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.project / "CLAUDE.md").exists())
        self.assertTrue((self.project / ".formic" / "board.json").is_file())
        self.assertTrue((self.project / "AGENTS.md").is_file())

    def test_local_skills_claude_goes_to_claude_folder(self):
        self.claude_install()
        r = self.run_install("init", str(self.project), "--local-skills")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        links = [p for p in (self.project / ".claude" / "skills").iterdir() if p.is_symlink()]
        self.assertEqual(len(links), SKILL_COUNT)
        self.assertFalse((self.project / ".opencode").exists())

    def test_local_skills_opencode_goes_to_opencode_folder(self):
        self.opencode_install()
        r = self.run_install("init", str(self.project), "--local-skills")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        links = [p for p in (self.project / ".opencode" / "skills").iterdir() if p.is_symlink()]
        self.assertEqual(len(links), SKILL_COUNT)
        self.assertFalse((self.project / ".claude").exists())


if __name__ == "__main__":
    unittest.main()
