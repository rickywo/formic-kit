#!/usr/bin/env python3
"""Tests for skills/formic-dispatch/scripts/send_brief.sh. Run: python3 -m unittest discover -s tests"""

import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "formic-dispatch" / "scripts" / "send_brief.sh"
SID = "11111111-2222-3333-4444-555555555555"
NAME = "worker-test"
DELIVERY = 4
IDLE = '{"result":{"agent":{"agent_status":"idle"}}}'

BRIEF = """You are a worker for formic-kit. Do one step of one task, then report.

- Task id: t-12
- Task folder: .formic/tasks/t-12_add-export-button-with-a-long-name
- Step: execute
- Round: 1 of 5

Load the skill `formic-execute` with the skill tool and follow it.
"""

# Stub herdr. Driven by files next to it: agent.json, prompt_mode, pane.txt, brief_text,
# on_enter (transcript path to append a user entry to on enter). Logs every call.
STUB = r"""#!/bin/bash
here="$(dirname "$0")"
echo "$*" >> "$here/calls.log"
case "$1 $2" in
  "agent get") cat "$here/agent.json" ;;
  "agent prompt")
    case "$(cat "$here/prompt_mode")" in
      run) sleep 1; echo '{"result":{"agent":{"agent_status":"idle"}}}' ;;
      working) sleep 1; echo '{"result":{"agent":{"agent_status":"working"}}}' ;;
      timeout) sleep 2; echo '{"error":{"code":"timeout"}}'; exit 1 ;;
      stall) echo '{"error":{"code":"agent_prompt_stalled"}}'; exit 1 ;;
      hang) exec sleep 30 ;;
    esac ;;
  "agent read") cat "$here/pane.txt" ;;
  "agent send-keys")
    if [ -f "$here/on_enter" ]; then
      python3 - "$(cat "$here/on_enter")" "$here/brief_text" <<'PY'
import json, sys
text = open(sys.argv[2]).read()
with open(sys.argv[1], "a") as f:
    f.write(json.dumps({"type": "user", "message": {"role": "user", "content": text}}) + "\n")
PY
    fi ;;
  "agent wait") echo '{"result":{"agent":{"agent_status":"idle"}}}' ;;
esac
exit 0
"""


class SendBriefCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.bin = self.dir / "bin"
        self.bin.mkdir()
        self.claude = self.dir / "claude"
        self.transcript = self.claude / "projects" / "-tmp-proj" / f"{SID}.jsonl"
        self.transcript.parent.mkdir(parents=True)
        self.brief = self.dir / "brief.md"
        self.brief.write_text(BRIEF)
        (self.bin / "herdr").write_text(STUB)
        (self.bin / "herdr").chmod(0o755)
        (self.bin / "brief_text").write_text(BRIEF)
        self.set_agent("claude")
        self.set_prompt("run")
        self.set_pane("")

    def tearDown(self):
        self.tmp.cleanup()

    # --- stub setup
    def set_agent(self, tool, session=SID, status="idle"):
        agent = {"agent_status": status}
        if tool:
            agent["agent_session"] = {"agent": tool, "value": session}
        (self.bin / "agent.json").write_text(json.dumps({"result": {"agent": agent}}))

    def set_prompt(self, mode):
        (self.bin / "prompt_mode").write_text(mode)

    def set_pane(self, text):
        (self.bin / "pane.txt").write_text(text)

    def enter_adds_entry(self):
        (self.bin / "on_enter").write_text(str(self.transcript))

    def add_entry(self, content, kind="user", path=None, **extra):
        with open(path or self.transcript, "a") as f:
            f.write(json.dumps({"type": kind, "message": {"role": kind, "content": content},
                                **extra}) + "\n")

    def wrapped_pane(self, prompt=True):
        """The brief hard-wrapped in the input box: scrollback, then the prompt line."""
        flat = BRIEF.replace("\n", " ")
        chunks = [flat[i:i + 37] for i in range(0, len(flat), 37)]
        head = "worker output so far\n" if prompt else ""
        return head + ("\u276f " if prompt else "") + "\n".join(chunks) + "\n"

    # --- running
    def run_script(self, brief=None, timeout_ms="20000", env_set=None, env_drop=()):
        env = dict(os.environ, HERDR_BIN_PATH=str(self.bin / "herdr"),
                   FORMIC_CLAUDE_DIR=str(self.claude), HOME=str(self.dir / "home"),
                   FORMIC_DELIVERY_SECONDS=str(DELIVERY), FORMIC_POLL_SECONDS="1")
        env.update(env_set or {})
        for key in env_drop:
            env.pop(key, None)
        started = time.time()
        r = subprocess.run(["bash", str(SCRIPT), NAME, str(brief or self.brief), timeout_ms],
                           capture_output=True, text=True, timeout=60, env=env)
        self.elapsed = time.time() - started
        return r

    def calls(self):
        log = self.bin / "calls.log"
        return log.read_text().splitlines() if log.exists() else []

    def send_keys(self):
        return [c for c in self.calls() if c.startswith("agent send-keys")]

    def assert_only_enter(self):
        for c in self.send_keys():
            self.assertEqual(c, f"agent send-keys {NAME} enter")

    # --- Claude Code
    def test_claude_delivered_at_once(self):
        self.add_entry(BRIEF)
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertIs(out["delivered"], True)
        self.assertEqual(out["sessionId"], SID)
        self.assertEqual(out["status"], "idle")
        self.assertEqual(self.send_keys(), [])
        self.assertFalse([c for c in self.calls() if c.startswith("agent read")])

    def test_claude_delivered_only_after_enter(self):
        self.set_pane(self.wrapped_pane())
        self.enter_adds_entry()
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertIs(out["delivered"], True)
        self.assertEqual(out["sessionId"], SID)
        self.assertEqual(self.send_keys(), [f"agent send-keys {NAME} enter"])
        self.assertIn(f"agent read {NAME} --source visible --lines 45", self.calls())

    def test_claude_pane_output_is_json(self):
        self.set_pane(json.dumps({"result": {"read": {"text": self.wrapped_pane()}}}))
        self.enter_adds_entry()
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIs(json.loads(r.stdout)["delivered"], True)
        self.assertEqual(self.send_keys(), [f"agent send-keys {NAME} enter"])

    def test_claude_never_delivered_not_visible(self):
        self.set_pane("Do you trust this folder?\n1. Yes\n2. No\n")
        self.set_prompt("hang")
        r = self.run_script()
        self.assertEqual(r.returncode, 3, r.stderr)
        out = json.loads(r.stdout)
        self.assertIs(out["delivered"], False)
        self.assertIn("never recorded", out["reason"])
        self.assertEqual(self.send_keys(), [])

    def test_claude_visible_but_enter_does_not_help(self):
        self.set_pane(self.wrapped_pane())
        self.set_prompt("hang")
        (self.bin / "on_enter").write_text(str(self.dir / "elsewhere.jsonl"))
        r = self.run_script()
        self.assertEqual(r.returncode, 3, r.stderr)
        out = json.loads(r.stdout)
        self.assertIs(out["delivered"], False)
        self.assertIn("never recorded", out["reason"])
        self.assertEqual(self.send_keys(), [f"agent send-keys {NAME} enter"])

    def test_claude_stalled_prompt_then_wait(self):
        self.set_prompt("stall")
        self.set_pane(self.wrapped_pane())
        self.enter_adds_entry()
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertIs(out["delivered"], True)
        self.assertEqual(out["status"], "idle")
        self.assertEqual(out["herdr"], json.loads(IDLE))
        waits = [c for c in self.calls() if c.startswith(f"agent wait {NAME} --timeout ")]
        self.assertEqual(len(waits), 1)
        self.assertEqual(self.send_keys(), [f"agent send-keys {NAME} enter"])

    def test_claude_transcript_starts_with_first_200_characters(self):
        long_brief = BRIEF + "Extra instruction line. " * 20
        self.brief.write_text(long_brief)
        self.assertGreater(len(long_brief.strip()), 200)
        # The comparison collapses whitespace, so the prefix is taken from the collapsed text.
        self.add_entry(" ".join(long_brief.split())[:200] + " (normalised tail)")
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIs(json.loads(r.stdout)["delivered"], True)
        self.assertEqual(self.send_keys(), [])

    def test_claude_other_user_entry_is_not_the_brief(self):
        self.add_entry("some other prompt")
        self.add_entry(BRIEF, kind="assistant")
        self.set_prompt("hang")
        r = self.run_script()
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIs(json.loads(r.stdout)["delivered"], False)

    def test_claude_list_content_user_entry_is_delivered(self):
        self.add_entry([{"type": "text", "text": BRIEF.replace("\n", "\n\n")}])
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIs(json.loads(r.stdout)["delivered"], True)
        self.assertEqual(self.send_keys(), [])

    def test_claude_list_content_with_several_text_parts(self):
        lines = BRIEF.strip().split("\n")
        parts = [{"type": "text", "text": "\n".join(lines[:3])},
                 {"type": "image", "source": "x"},
                 {"type": "text", "text": "\n".join(lines[3:])}]
        self.add_entry(parts)
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIs(json.loads(r.stdout)["delivered"], True)

    # Claude Code 2.1.x stores a pasted prompt inside a <pasted_content id="..."> envelope.
    @staticmethod
    def pasted(text, open_id="6da3", close_id=None):
        close_id = open_id if close_id is None else close_id
        return (f'\n\n<pasted_content id="{open_id}">\n{text}'
                f'</pasted_content id="{close_id}">\n')

    def test_claude_pasted_content_brief_is_delivered(self):
        # A real brief starts with the step's slash word, as in the observed transcript.
        self.brief.write_text("/formic-brief\n" + BRIEF)
        self.add_entry(self.pasted("/formic-brief\n" + BRIEF))
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIs(json.loads(r.stdout)["delivered"], True)
        self.assertEqual(self.send_keys(), [])

    def test_claude_pasted_content_exact_brief_is_delivered(self):
        self.add_entry([{"type": "text", "text": self.pasted(BRIEF)}])
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIs(json.loads(r.stdout)["delivered"], True)
        self.assertEqual(self.send_keys(), [])

    def test_claude_pasted_content_unrelated_text_is_not_the_brief(self):
        self.add_entry(self.pasted("/formic-brief\nsome other prompt\n"))
        self.set_prompt("hang")
        r = self.run_script()
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIs(json.loads(r.stdout)["delivered"], False)

    def test_claude_pasted_content_with_mismatched_ids_is_not_the_brief(self):
        self.brief.write_text("/formic-brief\n" + BRIEF)
        self.add_entry(self.pasted("/formic-brief\n" + BRIEF, open_id="6da3", close_id="9f01"))
        self.set_prompt("hang")
        r = self.run_script()
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIs(json.loads(r.stdout)["delivered"], False)

    def test_claude_tool_result_list_is_not_the_brief(self):
        self.add_entry([{"type": "tool_result", "tool_use_id": "t1", "content": BRIEF}])
        self.set_prompt("hang")
        r = self.run_script()
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIs(json.loads(r.stdout)["delivered"], False)

    def test_claude_meta_entries_are_skipped(self):
        self.add_entry(BRIEF, isMeta=True)
        self.add_entry([{"type": "text", "text": BRIEF}], isMeta=True)
        self.set_prompt("hang")
        r = self.run_script()
        self.assertEqual(r.returncode, 3, r.stderr)
        out = json.loads(r.stdout)
        self.assertIs(out["delivered"], False)
        self.assertIn("never recorded", out["reason"])

    def test_claude_non_meta_entry_after_meta_entries_counts(self):
        self.add_entry(BRIEF, isMeta=True)
        self.add_entry(BRIEF, isMeta=False)
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIs(json.loads(r.stdout)["delivered"], True)

    def test_claude_config_dir_is_used_when_formic_claude_dir_is_unset(self):
        config = self.dir / "config"
        path = config / "projects" / "-tmp-proj" / f"{SID}.jsonl"
        path.parent.mkdir(parents=True)
        self.add_entry(BRIEF, path=path)
        r = self.run_script(env_set={"CLAUDE_CONFIG_DIR": str(config)}, env_drop=("FORMIC_CLAUDE_DIR",))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIs(json.loads(r.stdout)["delivered"], True)

    def test_formic_claude_dir_beats_claude_config_dir(self):
        config = self.dir / "config"
        path = config / "projects" / "-tmp-proj" / f"{SID}.jsonl"
        path.parent.mkdir(parents=True)
        self.add_entry(BRIEF, path=path)  # only the config directory has the brief
        self.set_prompt("hang")
        r = self.run_script(env_set={"CLAUDE_CONFIG_DIR": str(config)})
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIs(json.loads(r.stdout)["delivered"], False)

    def test_home_dot_claude_is_the_fallback(self):
        path = self.dir / "home" / ".claude" / "projects" / "-tmp-proj" / f"{SID}.jsonl"
        path.parent.mkdir(parents=True)
        self.add_entry(BRIEF, path=path)
        r = self.run_script(env_drop=("FORMIC_CLAUDE_DIR", "CLAUDE_CONFIG_DIR"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIs(json.loads(r.stdout)["delivered"], True)

    # --- Enter recovery
    def assert_no_enter(self):
        r = self.run_script()
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIs(json.loads(r.stdout)["delivered"], False)
        self.assertEqual(self.send_keys(), [])

    def test_enter_not_pressed_when_agent_is_blocked(self):
        self.set_agent("claude", status="blocked")
        self.set_pane(self.wrapped_pane())
        self.enter_adds_entry()
        self.set_prompt("hang")
        self.assert_no_enter()

    def test_enter_not_pressed_when_agent_is_working(self):
        self.set_agent("claude", status="working")
        self.set_pane(self.wrapped_pane())
        self.enter_adds_entry()
        self.set_prompt("hang")
        self.assert_no_enter()

    def test_enter_not_pressed_when_brief_is_only_above_the_last_prompt_line(self):
        self.set_pane(self.wrapped_pane(prompt=False) + "\u276f \nesc to interrupt\n")
        self.enter_adds_entry()
        self.set_prompt("hang")
        self.assert_no_enter()

    def test_enter_not_pressed_without_any_prompt_line(self):
        self.set_pane(self.wrapped_pane(prompt=False))
        self.enter_adds_entry()
        self.set_prompt("hang")
        self.assert_no_enter()

    def test_enter_not_pressed_while_a_dialog_is_showing(self):
        for dialog in ("Esc to cancel", "Do you want to proceed?", "Enter to confirm",
                       "\u276f 1. Yes\n  2. No"):
            with self.subTest(dialog=dialog):
                log = self.bin / "calls.log"
                if log.exists():
                    log.unlink()
                self.set_pane(self.wrapped_pane() + dialog + "\n")
                self.enter_adds_entry()
                self.set_prompt("hang")
                self.assert_no_enter()

    def test_enter_pressed_for_a_pasted_text_placeholder(self):
        self.set_pane("worker output so far\n\u276f [Pasted text #1 +12 lines]\n")
        self.enter_adds_entry()
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIs(json.loads(r.stdout)["delivered"], True)
        self.assertEqual(self.send_keys(), [f"agent send-keys {NAME} enter"])

    def test_enter_not_pressed_for_a_pasted_text_placeholder_above_the_prompt(self):
        self.set_pane("[Pasted text #1 +12 lines]\n\u276f \n")
        self.enter_adds_entry()
        self.set_prompt("hang")
        self.assert_no_enter()

    # --- timeout
    def test_still_working_after_the_wait_is_a_timeout_for_claude(self):
        self.set_agent("claude", status="working")
        self.add_entry(BRIEF)
        self.set_prompt("timeout")
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertIs(out["delivered"], True)
        self.assertEqual(out["status"], "timeout")
        self.assertEqual(out["agentStatus"], "working")

    def test_still_working_after_the_wait_is_a_timeout_for_opencode(self):
        self.set_agent("opencode", "ses_abc", status="working")
        self.set_prompt("working")
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["status"], "timeout")
        self.assertEqual(out["agentStatus"], "working")

    def test_agent_status_is_only_reported_for_a_timeout(self):
        self.add_entry(BRIEF)
        out = json.loads(self.run_script().stdout)
        self.assertEqual(out["status"], "idle")
        self.assertNotIn("agentStatus", out)

    # --- opencode
    def test_opencode_with_session(self):
        self.set_agent("opencode", "ses_abc")
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertIs(out["delivered"], True)
        self.assertEqual(out["sessionId"], "ses_abc")
        self.assertEqual(out["status"], "idle")
        self.assertFalse([c for c in self.calls() if c.startswith("agent read")])
        self.assertEqual(self.send_keys(), [])

    def test_opencode_without_session(self):
        self.set_agent(None)
        self.set_prompt("hang")
        r = self.run_script()
        self.assertEqual(r.returncode, 3, r.stderr)
        out = json.loads(r.stdout)
        self.assertIs(out["delivered"], False)
        self.assertIn("no session", out["reason"])
        self.assertGreaterEqual(self.elapsed, DELIVERY - 1)
        self.assertFalse([c for c in self.calls() if c.startswith("agent read")])
        self.assertEqual(self.send_keys(), [])

    # --- usage
    def test_missing_brief_file_is_a_usage_error(self):
        r = self.run_script(brief=self.dir / "missing.md")
        self.assertEqual(r.returncode, 1)
        self.assertIn("usage", r.stderr)

    def test_every_key_sent_is_a_single_enter(self):
        self.set_pane(self.wrapped_pane())
        self.enter_adds_entry()
        self.run_script()
        self.assert_only_enter()
        self.assertLessEqual(len(self.send_keys()), 1)


if __name__ == "__main__":
    unittest.main()
