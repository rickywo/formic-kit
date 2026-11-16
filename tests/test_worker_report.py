#!/usr/bin/env python3
"""Tests for skills/formic-dispatch/scripts/worker_report.py. Run: python3 -m unittest discover -s tests"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "formic-dispatch" / "scripts" / "worker_report.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "claude"
SID = "11111111-2222-3333-4444-555555555555"
NO_MESSAGE = "(the last turn ended with no final message)"
OPENCODE_EXPORT = {"messages": [{"info": {"role": "assistant", "agent": "worker-sonnet", "modelID": "m"},
                                 "parts": [{"type": "text", "text": "DONE ok"}]}]}


class WorkerReportCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.claude = self.dir / "claude"
        self.home = self.dir / "home"
        self.bin = self.dir / "bin"
        self.home.mkdir()
        self.bin.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def install_fixture(self, name, sid=SID, folder="-tmp-proj"):
        dest = self.claude / "projects" / folder / f"{sid}.jsonl"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(FIXTURES / f"{name}.jsonl", dest)
        return dest

    def stub(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/bash\n" + body)
        path.chmod(0o755)
        return path

    def stub_herdr(self, agent_json):
        payload = json.dumps({"result": {"agent": agent_json}})
        return self.stub("herdr", f"cat <<'EOF'\n{payload}\nEOF\n")

    def stub_opencode(self, export=OPENCODE_EXPORT):
        return self.stub("opencode", f"cat <<'EOF'\n{json.dumps(export)}\nEOF\n")

    def run_script(self, *args, env_set=None, env_drop=()):
        env = dict(os.environ, HOME=str(self.home), FORMIC_CLAUDE_DIR=str(self.claude),
                   PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}")
        env.update(env_set or {})
        for key in env_drop:
            env.pop(key, None)
        env.pop("HERDR_BIN_PATH", None)
        if (self.bin / "herdr").exists():
            env["HERDR_BIN_PATH"] = str(self.bin / "herdr")
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env)

    def report(self, *args, **env):
        r = self.run_script(*args, **env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def claude_report(self, fixture, sid=SID):
        self.install_fixture(fixture, sid)
        return self.report("--session", sid, "--tool", "claude")


class ClaudeTranscriptTests(WorkerReportCase):
    def test_normal_run(self):
        out = self.claude_report("normal")
        self.assertEqual(out, {
            "sessionId": SID, "agentStatus": None, "agent": "worker-sonnet", "model": "test-model-1",
            "verdict": "DONE", "message": "DONE\nAll good.", "error": None, "errorKind": None,
        })

    def test_credentials_error(self):
        out = self.claude_report("error_credentials")
        self.assertEqual(out["verdict"], "ERROR")
        self.assertIn("security token", out["error"])
        self.assertEqual(out["errorKind"], "credentials")
        self.assertEqual(out["message"], NO_MESSAGE)

    def test_invalid_model_error_is_other(self):
        out = self.claude_report("error_model")
        self.assertEqual(out["verdict"], "ERROR")
        self.assertIn("model identifier is invalid", out["error"])
        self.assertEqual(out["errorKind"], "other")

    def test_no_assistant_text(self):
        out = self.claude_report("tool_use_only")
        self.assertEqual(out["verdict"], "NONE")
        self.assertEqual(out["message"], NO_MESSAGE)
        self.assertIsNone(out["error"])
        self.assertIsNone(out["errorKind"])
        self.assertEqual(out["model"], "test-model-1")
        self.assertIsNone(out["agent"])

    def test_streamed_final_message(self):
        out = self.claude_report("streamed")
        self.assertEqual(out["verdict"], "DONE")
        self.assertEqual(out["message"], "DONE\nstreamed result")

    def test_error_followed_by_normal_entry(self):
        out = self.claude_report("error_then_ok")
        self.assertEqual(out["verdict"], "BLOCKED")
        self.assertEqual(out["message"], "BLOCKED need an answer")
        self.assertIsNone(out["error"])
        self.assertIsNone(out["errorKind"])

    def test_no_prompt_is_not_delivered(self):
        out = self.claude_report("no_prompt")
        self.assertEqual(out["verdict"], "NOT_DELIVERED")
        self.assertEqual(out["sessionId"], SID)
        self.assertEqual(set(out), {"sessionId", "agentStatus", "verdict", "message"})

    def test_missing_transcript_is_not_delivered(self):
        out = self.report("--session", SID, "--tool", "claude")
        self.assertEqual(out["verdict"], "NOT_DELIVERED")

    def test_newest_transcript_wins(self):
        old = self.install_fixture("normal", folder="-tmp-old")
        new = self.install_fixture("streamed", folder="-tmp-new")
        os.utime(old, (1000, 1000))
        os.utime(new, (2000, 2000))
        self.assertEqual(self.report("--session", SID, "--tool", "claude")["message"], "DONE\nstreamed result")
        os.utime(old, (3000, 3000))
        self.assertEqual(self.report("--session", SID, "--tool", "claude")["message"], "DONE\nAll good.")

    def test_garbage_lines_are_skipped(self):
        dest = self.install_fixture("normal")
        text = dest.read_text()
        self.assertIn("this line is not json", text)
        dest.write_text("\n" + text + "[1, 2]\n\"str\"\n")
        self.assertEqual(self.report("--session", SID, "--tool", "claude")["verdict"], "DONE")

    def test_verdict_strips_markup(self):
        dest = self.install_fixture("normal")
        lines = dest.read_text().splitlines()
        last = json.loads(lines[-1])
        last["message"]["content"] = [{"type": "text", "text": "**Partial:** half done"}]
        dest.write_text("\n".join(lines[:-1] + [json.dumps(last)]) + "\n")
        self.assertEqual(self.report("--session", SID, "--tool", "claude")["verdict"], "PARTIAL")

    def test_error_field_used_when_no_text(self):
        dest = self.install_fixture("error_model")
        lines = dest.read_text().splitlines()
        last = json.loads(lines[-1])
        last["message"]["content"] = []
        last["error"] = "authentication_failed"
        dest.write_text("\n".join(lines[:-1] + [json.dumps(last)]) + "\n")
        out = self.report("--session", SID, "--tool", "claude")
        self.assertEqual(out["verdict"], "ERROR")
        self.assertEqual(out["error"], "authentication_failed")
        self.assertEqual(out["errorKind"], "credentials")

    def test_list_content_user_entry_is_delivered(self):
        out = self.claude_report("list_content")
        self.assertEqual(out["verdict"], "DONE")
        self.assertEqual(out["message"], "DONE\nlisted")

    def test_meta_only_user_entries_are_not_delivered(self):
        out = self.claude_report("meta_only")
        self.assertEqual(out["verdict"], "NOT_DELIVERED")
        self.assertEqual(set(out), {"sessionId", "agentStatus", "verdict", "message"})

    def test_tool_result_only_user_entries_are_not_delivered(self):
        dest = self.install_fixture("normal")
        kept = [l for l in dest.read_text().splitlines() if '"tool_result"' in l]
        dest.write_text("\n".join(kept) + "\n")
        self.assertEqual(self.report("--session", SID, "--tool", "claude")["verdict"], "NOT_DELIVERED")

    def test_credential_fixtures(self):
        for name in ("auth_failed_field", "invalid_api_key", "please_login", "oauth_expired"):
            with self.subTest(fixture=name):
                out = self.claude_report(name)
                self.assertEqual(out["verdict"], "ERROR")
                self.assertEqual(out["errorKind"], "credentials")
                self.assertEqual(out["message"], NO_MESSAGE)
                self.assertTrue(out["error"])

    def test_auth_failed_entry_is_not_a_final_message(self):
        out = self.claude_report("auth_failed_field")
        self.assertEqual(out["error"], "Something went wrong")


class TranscriptDirectoryTests(WorkerReportCase):
    def place(self, root):
        dest = Path(root) / "projects" / "-tmp-proj" / f"{SID}.jsonl"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(FIXTURES / "normal.jsonl", dest)
        return dest

    def test_claude_config_dir_used_when_formic_claude_dir_is_unset(self):
        config = self.dir / "config"
        self.place(config)
        out = self.report("--session", SID, "--tool", "claude",
                          env_set={"CLAUDE_CONFIG_DIR": str(config)}, env_drop=("FORMIC_CLAUDE_DIR",))
        self.assertEqual(out["verdict"], "DONE")

    def test_formic_claude_dir_beats_claude_config_dir(self):
        config = self.dir / "config"
        self.place(config)
        # FORMIC_CLAUDE_DIR (self.claude) has no transcript, so the config one must not be read.
        out = self.report("--session", SID, "--tool", "claude",
                          env_set={"CLAUDE_CONFIG_DIR": str(config)})
        self.assertEqual(out["verdict"], "NOT_DELIVERED")
        self.place(self.claude)
        out = self.report("--session", SID, "--tool", "claude",
                          env_set={"CLAUDE_CONFIG_DIR": str(config)})
        self.assertEqual(out["verdict"], "DONE")

    def test_home_dot_claude_is_the_fallback(self):
        self.place(self.home / ".claude")
        out = self.report("--session", SID, "--tool", "claude",
                          env_drop=("FORMIC_CLAUDE_DIR", "CLAUDE_CONFIG_DIR"))
        self.assertEqual(out["verdict"], "DONE")

    def test_empty_variables_are_ignored(self):
        self.place(self.home / ".claude")
        out = self.report("--session", SID, "--tool", "claude",
                          env_set={"FORMIC_CLAUDE_DIR": "", "CLAUDE_CONFIG_DIR": ""})
        self.assertEqual(out["verdict"], "DONE")


class ToolSelectionTests(WorkerReportCase):
    def test_by_agent_name_uses_claude_transcript(self):
        self.install_fixture("normal")
        self.stub_herdr({"agent": "w1", "agent_status": "idle",
                         "agent_session": {"agent": "claude", "value": SID}})
        out = self.report("w1")
        self.assertEqual(out["verdict"], "DONE")
        self.assertEqual(out["agent"], "worker-sonnet")
        self.assertEqual(out["agentStatus"], "idle")

    def test_by_agent_name_claude_without_transcript(self):
        self.stub_herdr({"agent": "w1", "agent_status": "idle",
                         "agent_session": {"agent": "claude", "value": SID}})
        self.assertEqual(self.report("w1")["verdict"], "NOT_DELIVERED")

    def test_by_agent_name_without_session_value(self):
        self.stub_herdr({"agent": "w1", "agent_status": "idle", "agent_session": {"agent": "claude"}})
        out = self.report("w1")
        self.assertEqual(out["verdict"], "NOT_DELIVERED")
        self.assertIsNone(out["sessionId"])

    def test_herdr_without_agent_field_falls_back_to_opencode(self):
        self.install_fixture("error_model")  # must not be read
        self.stub_herdr({"agent": "w1", "agent_status": "idle", "agent_session": {"value": SID}})
        self.stub_opencode()
        out = self.report("w1")
        self.assertEqual(out["verdict"], "DONE")
        self.assertEqual(out["agent"], "worker-sonnet")

    def test_herdr_failure_is_an_error(self):
        self.stub("herdr", "echo nope >&2\nexit 3\n")
        r = self.run_script("w1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("herdr agent get w1 failed", r.stderr)


class OpencodeTests(WorkerReportCase):
    def test_stub_opencode_export(self):
        self.stub_opencode()
        out = self.report("--session", "ses_abc")
        self.assertEqual(out, {
            "sessionId": "ses_abc", "agentStatus": None, "agent": "worker-sonnet", "model": "m",
            "verdict": "DONE", "message": "DONE ok", "error": None, "errorKind": None,
        })

    def test_session_without_tool_ignores_claude_transcript(self):
        self.install_fixture("error_model")
        self.stub_opencode()
        self.assertEqual(self.report("--session", SID)["verdict"], "DONE")
        self.assertEqual(self.report("--session", SID, "--tool", "opencode")["verdict"], "DONE")

    def test_tool_before_session(self):
        self.install_fixture("normal")
        self.assertEqual(self.report("--tool", "claude", "--session", SID)["verdict"], "DONE")

    def test_opencode_error_kinds(self):
        export = {"messages": [{"info": {"role": "assistant", "agent": "a", "modelID": "m",
                                         "error": {"name": "APIError",
                                                   "data": {"message": "The security token included in the request is expired"}}},
                                "parts": []}]}
        self.stub_opencode(export)
        out = self.report("--session", "ses_abc")
        self.assertEqual((out["verdict"], out["errorKind"]), ("ERROR", "credentials"))


class UsageTests(WorkerReportCase):
    def assert_usage(self, *args):
        r = self.run_script(*args)
        self.assertEqual(r.returncode, 1, args)
        self.assertIn("usage: worker_report.py", r.stderr)

    def test_usage_errors(self):
        self.assert_usage()
        self.assert_usage("--session")
        self.assert_usage("--tool", "claude")
        self.assert_usage("--session", SID, "--tool", "codex")
        self.assert_usage("--session", SID, "--tool")
        self.assert_usage("--session", SID, "extra")
        self.assert_usage("a", "b")
        self.assert_usage("--bogus")


class CredentialPatternTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("worker_report", SCRIPT)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def test_credential_wordings_match(self):
        for text in (
            "The security token included in the request is expired",
            "Unable to locate credentials",
            "AccessDenied: the security token is not valid",
            "Missing credentials in config",
            "Missing AWS credentials",
            "Run aws sso login to continue",
            "The SSO session has expired",
            "SSO token is expired or invalid",
            "Token has expired and refresh failed",
            "Invalid API key",
            "Not logged in - Please run /login",
            "OAuth token has expired. Please obtain a new token",
            "authentication_failed",
            "Authentication failed",
        ):
            self.assertTrue(self.mod.CREDENTIAL_PATTERNS.search(text), text)

    def test_invalid_model_identifier_does_not_match(self):
        self.assertIsNone(self.mod.CREDENTIAL_PATTERNS.search(
            "API Error (test/model): 400 The provided model identifier is invalid."))


if __name__ == "__main__":
    unittest.main()
