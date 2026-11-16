#!/usr/bin/env python3
"""Tests for skills/formic-dispatch/scripts/allowed_tools.py. Run: python3 tests/test_allowed_tools.py"""

import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "formic-dispatch" / "scripts" / "allowed_tools.py"

GIT = [
    "Bash(git status:*)",
    "Bash(git diff:*)",
    "Bash(git log:*)",
    "Bash(git show:*)",
    "Bash(git rev-parse:*)",
]

UNITTEST_CMD = "python3 -m unittest discover -s tests -v"
BASH_N_CMD = 'bash -n "$f" || exit 1'
SHELLCHECK_CMD = ("shellcheck -S warning install.sh plugin/*.sh skills/*/scripts/*.sh "
                  "(main already has warnings in 3 files; compare against the safe point)")


class AllowedToolsCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write_project(self, data):
        folder = self.root / ".formic"
        folder.mkdir(exist_ok=True)
        text = data if isinstance(data, str) else json.dumps(data)
        (folder / "project.json").write_text(text, encoding="utf-8")

    def run_script(self, *args, project=None):
        project = self.root if project is None else project
        return subprocess.run([sys.executable, str(SCRIPT), "--project", str(project), *args],
                              capture_output=True, text=True)

    def entries(self, commands, project=None):
        """Write a project.json with these commands and return the --list entries."""
        self.write_project({"commands": commands})
        r = self.run_script("--list", project=project)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.splitlines()

    def check_entries(self, commands):
        """Return the entries after the five git ones."""
        got = self.entries(commands)
        self.assertEqual(got[:5], GIT)
        return got[5:]

    # no project.json, no commands

    def test_no_project_json(self):
        r = self.run_script("--list")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines(), GIT)

    def test_commands_missing(self):
        self.write_project({"schemaVersion": 1})
        r = self.run_script("--list")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines(), GIT)

    def test_commands_null(self):
        self.write_project({"commands": None})
        r = self.run_script("--list")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines(), GIT)

    def test_default_project_is_current_directory(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--list"], capture_output=True,
                           text=True, cwd=str(self.root))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines(), GIT)

    # sample commands

    def test_unittest_command(self):
        self.assertEqual(self.check_entries({"test": UNITTEST_CMD}),
                         ["Bash(python3 -m unittest discover -s tests -v:*)"])

    def test_bash_n_with_variable_and_exit(self):
        self.assertEqual(self.check_entries({"typecheck": BASH_N_CMD}), ["Bash(bash -n:*)"])

    def test_shellcheck_with_trailing_prose(self):
        self.assertEqual(self.check_entries({"extraTests": [{"when": "x", "command": SHELLCHECK_CMD}]}),
                         ["Bash(shellcheck -S warning install.sh:*)"])

    def test_for_loop_gives_only_the_inner_command(self):
        cmd = 'for f in a b; do bash -n "$f" || exit 1; done'
        self.assertEqual(self.check_entries({"typecheck": cmd}), ["Bash(bash -n:*)"])

    def test_multiline_loop(self):
        cmd = 'for f in a b\ndo\n  bash -n "$f"\ndone\nif true; then cd x; fi'
        self.assertEqual(self.check_entries({"typecheck": cmd}), ["Bash(bash -n:*)"])

    def test_separators_split(self):
        cmd = "ruff check . && mypy src | tee out.txt; npm test || echo failed"
        self.assertEqual(self.check_entries({"typecheck": cmd}), [
            "Bash(ruff check .:*)",
            "Bash(mypy src:*)",
            "Bash(npm test:*)",
            "Bash(echo failed:*)",
        ])

    def test_pipe_sinks_get_no_rule(self):
        self.assertEqual(self.check_entries({"test": "a | tee out.txt"}), ["Bash(a:*)"])
        self.assertEqual(self.check_entries({"test": "a | xargs b"}), ["Bash(a:*)"])
        self.assertEqual(self.check_entries({"test": "a | sponge out.txt"}), ["Bash(a:*)"])
        self.assertEqual(self.check_entries({"test": "a | b | tee out.txt"}), ["Bash(a:*)", "Bash(b:*)"])

    def test_pipe_sink_after_other_separators_is_not_a_sink_position(self):
        # Only a command right after a single pipe is a sink; `;`, `&&` and `||` start a new pipeline.
        self.assertEqual(self.check_entries({"test": "a && tee out.txt"}),
                         ["Bash(a:*)", "Bash(tee out.txt:*)"])
        self.assertEqual(self.check_entries({"test": "a || tee out.txt"}),
                         ["Bash(a:*)", "Bash(tee out.txt:*)"])
        self.assertEqual(self.check_entries({"test": "a | b; tee out.txt"}),
                         ["Bash(a:*)", "Bash(b:*)", "Bash(tee out.txt:*)"])

    def test_and_chain_gives_a_rule_for_each_command(self):
        self.assertEqual(self.check_entries({"test": "a && b"}), ["Bash(a:*)", "Bash(b:*)"])

    def test_interpreter_with_eval_flag_gets_no_rule(self):
        for cmd in ('bash -c "x"', "sh -c x", "zsh -c x", "python3 -c 'print(1)'", "python -c x",
                    "perl -e x", "node -e x", "node -p 1", "node --eval x", "node --print 1",
                    "ruby -e x", "bash -lc x", "python3 -u -c x", "python3 -W ignore -c x",
                    "python3 -c"):
            with self.subTest(cmd=cmd):
                self.assertEqual(self.check_entries({"test": cmd}), [])

    def test_interpreter_running_a_script_gets_no_rule(self):
        for cmd in ("node script.js", "python3 script.py", "bash run.sh", "sh ./x.sh", "ruby a.rb",
                    "perl a.pl", "python3", "bash", "node"):
            with self.subTest(cmd=cmd):
                self.assertEqual(self.check_entries({"test": cmd}), [])

    def test_python_m_needs_a_module_name(self):
        self.assertEqual(self.check_entries({"test": "python3 -m $MOD"}), [])
        self.assertEqual(self.check_entries({"test": "python3 -m"}), [])
        self.assertEqual(self.check_entries({"test": "python3 -m pytest -q"}),
                         ["Bash(python3 -m pytest -q:*)"])

    def test_npx_needs_a_tool_name(self):
        self.assertEqual(self.check_entries({"test": "npx -y x"}), [])
        self.assertEqual(self.check_entries({"test": "npx"}), [])
        self.assertEqual(self.check_entries({"test": "npx tsc --noEmit"}), ["Bash(npx tsc --noEmit:*)"])
        self.assertEqual(self.check_entries({"test": "npx tsc -p tsconfig.json"}),
                         ["Bash(npx tsc -p tsconfig.json:*)"])

    def test_plain_commands_and_safe_interpreter_flags_keep_their_rules(self):
        self.assertEqual(self.check_entries({"test": "npm test"}), ["Bash(npm test:*)"])
        self.assertEqual(self.check_entries({"test": UNITTEST_CMD}),
                         ["Bash(python3 -m unittest discover -s tests -v:*)"])
        self.assertEqual(self.check_entries({"test": 'bash -n "$f"'}), ["Bash(bash -n:*)"])
        self.assertEqual(self.check_entries({"test": "python3 -m py_compile a.py b.py"}),
                         ["Bash(python3 -m py_compile a.py b.py:*)"])

    def test_c_and_e_flags_are_only_checked_for_interpreters(self):
        self.assertEqual(self.check_entries({"test": "grep -c x f"}), ["Bash(grep -c x f:*)"])
        self.assertEqual(self.check_entries({"test": "tool -e --eval -p"}), ["Bash(tool -e --eval -p:*)"])

    def test_interpreter_after_a_pipe_follows_the_same_rules(self):
        self.assertEqual(self.check_entries({"test": "a | python3 -c x"}), ["Bash(a:*)"])
        self.assertEqual(self.check_entries({"test": "a | python3 -m json.tool"}),
                         ["Bash(a:*)", "Bash(python3 -m json.tool:*)"])

    def test_dropped_interpreter_does_not_hide_the_rest_of_the_project_commands(self):
        got = self.check_entries({"typecheck": "bash -c 'x' && make lint",
                                  "test": "node run.js; npm test"})
        self.assertEqual(got, ["Bash(make lint:*)", "Bash(npm test:*)"])

    def test_no_rule_is_a_bare_interpreter(self):
        self.write_project({"commands": {"typecheck": "bash -c x; python3 -c y; node z.js; npx -y q",
                                         "test": "perl -e 1 | tee a; sh b.sh; zsh -c w; ruby -e v; python u.py"}})
        out = self.run_script("--list").stdout.splitlines()
        self.assertEqual(out, GIT)

    def test_separator_inside_quotes_does_not_split(self):
        self.assertEqual(self.check_entries({"test": 'grep -c "a && b" file.txt'}),
                         ["Bash(grep -c:*)"])

    def test_environment_assignment_is_dropped(self):
        self.assertEqual(self.check_entries({"test": "CI=1 pytest -q"}), ["Bash(pytest -q:*)"])

    # build, empty, duplicates

    def test_null_build_and_empty_test_are_skipped(self):
        got = self.check_entries({"typecheck": "tsc --noEmit", "build": None, "test": "  ",
                                  "extraTests": []})
        self.assertEqual(got, ["Bash(tsc --noEmit:*)"])

    def test_build_is_included(self):
        got = self.check_entries({"build": "npm run build"})
        self.assertEqual(got, ["Bash(npm run build:*)"])

    def test_malformed_extra_tests_are_skipped(self):
        got = self.check_entries({"extraTests": ["oops", {"when": "x"}, {"command": 5},
                                                 {"command": "make lint"}]})
        self.assertEqual(got, ["Bash(make lint:*)"])

    def test_duplicates_collapse_in_first_seen_order(self):
        got = self.check_entries({
            "typecheck": "tsc --noEmit",
            "test": "npm test && tsc --noEmit",
            "extraTests": [{"when": "x", "command": "npm test"}, {"when": "y", "command": "make lint"}],
        })
        self.assertEqual(got, ["Bash(tsc --noEmit:*)", "Bash(npm test:*)", "Bash(make lint:*)"])

    def test_git_command_in_project_collapses_into_git_entry(self):
        got = self.entries({"test": "git status && make test"})
        self.assertEqual(got, GIT + ["Bash(make test:*)"])

    # this repository's own project.json

    def test_this_repository_project_json(self):
        r = self.run_script("--list", project=ROOT)
        self.assertEqual(r.returncode, 0, r.stderr)
        got = r.stdout.splitlines()
        self.assertEqual(got[:5], GIT)
        self.assertIn("Bash(python3 -m unittest discover -s tests -v:*)", got)
        self.assertIn("Bash(shellcheck -S warning install.sh:*)", got)
        self.assertIn("Bash(bash -n:*)", got)
        for entry in got:
            self.assertTrue(entry.startswith("Bash(") and entry.endswith(":*)"), entry)
            prefix = entry[len("Bash("):-len(":*)")]
            self.assertNotIn("*", prefix, entry)
            self.assertNotIn("$", prefix, entry)
            self.assertNotIn("'", prefix, entry)
            self.assertNotIn('"', prefix, entry)
        for entry in got[5:]:
            self.assertNotIn("git", entry)

    # errors

    def test_invalid_json(self):
        self.write_project("{ not json")
        r = self.run_script("--list")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, "")
        self.assertIn("project.json", r.stderr)
        self.assertIn("invalid JSON", r.stderr)

    def test_top_level_not_an_object(self):
        self.write_project("[1, 2]")
        r = self.run_script()
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, "")
        self.assertIn("project.json", r.stderr)

    def test_commands_wrong_type(self):
        self.write_project({"commands": "make test"})
        r = self.run_script()
        self.assertEqual(r.returncode, 1)
        self.assertIn("commands", r.stderr)

    # output forms

    def test_list_form_is_one_unquoted_entry_per_line(self):
        self.write_project({"commands": {"test": UNITTEST_CMD}})
        r = self.run_script("--list")
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(lines, GIT + ["Bash(python3 -m unittest discover -s tests -v:*)"])
        for line in lines:
            self.assertNotIn("'", line)

    def test_one_line_form_is_quoted_and_round_trips(self):
        self.write_project({"commands": {"typecheck": BASH_N_CMD, "test": UNITTEST_CMD}})
        listed = self.run_script("--list").stdout.splitlines()
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.endswith("\n"))
        line = r.stdout[:-1]
        self.assertNotIn("\n", line)
        self.assertEqual(line, " ".join("'%s'" % e for e in listed))
        self.assertEqual(shlex.split(line), listed)

    def test_one_line_form_survives_a_real_shell(self):
        self.write_project({"commands": {"typecheck": BASH_N_CMD}})
        line = self.run_script().stdout.strip()
        r = subprocess.run(["bash", "-c", 'for a in %s; do printf "%%s\\n" "$a"; done' % line],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines(), self.run_script("--list").stdout.splitlines())

    # safety

    def test_never_edit_write_or_wildcard_bash(self):
        self.write_project({"commands": {"typecheck": BASH_N_CMD, "test": UNITTEST_CMD,
                                         "extraTests": [{"when": "x", "command": SHELLCHECK_CMD}]}})
        for args in (["--list"], []):
            out = self.run_script(*args).stdout
            self.assertNotIn("Edit", out)
            self.assertNotIn("Write", out)
            self.assertNotIn("Bash(*)", out)
            self.assertNotIn("dangerously", out)
        for entry in self.run_script("--list").stdout.splitlines():
            self.assertTrue(entry.startswith("Bash(") and entry.endswith(":*)"), entry)

    def test_shell_syntax_words_end_the_prefix(self):
        cases = {
            "make $(cat target)": "Bash(make:*)",
            "make `cat target`": "Bash(make:*)",
            "pytest -q > out.txt": "Bash(pytest -q:*)",
            "pytest -q 2>&1": "Bash(pytest -q:*)",
            "pytest 'a b' -q": "Bash(pytest:*)",
            "pytest tests/*.py": "Bash(pytest:*)",
            "pytest ${DIR}/x": "Bash(pytest:*)",
            "pytest a\\ b": "Bash(pytest:*)",
        }
        for cmd, expected in cases.items():
            with self.subTest(cmd=cmd):
                self.assertEqual(self.check_entries({"test": cmd}), [expected])

    def test_command_that_is_only_syntax_gives_no_entry(self):
        self.assertEqual(self.check_entries({"test": '"$X" && $(foo) && exit 1'}), [])

    def test_unbalanced_quote_does_not_crash(self):
        self.assertEqual(self.check_entries({"test": "pytest -q 'unclosed"}), ["Bash(pytest -q:*)"])


if __name__ == "__main__":
    unittest.main()
