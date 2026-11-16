#!/usr/bin/env python3
"""Print the Claude Code --allowedTools list for a formic-kit project.

Usage: allowed_tools.py [--project DIR] [--list]

Reads <DIR>/.formic/project.json (DIR defaults to the current directory) and prints
the Bash permission rules a Claude Code worker may use without a prompt:

  - the read-only git commands: git status, diff, log, show, rev-parse;
  - the project's check commands: commands.typecheck, commands.build, commands.test
    and every commands.extraTests[].command.

Each check command string is split into simple commands at &&, ||, ;, | and newlines
(outside quotes). Shell keywords are ignored. For each simple command the rule is the
longest leading run of words that contain no shell syntax character, written as
Bash(<words>:*). Duplicates are removed; the first occurrence keeps its place.

Some rules would let a worker run anything, so they are never printed:

  - a command that follows a pipe and is a pipe sink (tee, xargs, sponge);
  - a rule whose first word is an interpreter or shell (bash, sh, zsh, python, python3,
    node, ruby, perl, npx) unless it starts with a flag, as in `bash -n` or
    `python3 -m unittest`. `node script.js` and a bare `python3` give nothing. Such a
    rule is also dropped when its interpreter options include -c, -e, -p, --eval or
    --print (or a flag cluster that contains c or e), or when it ends at `-m` with no
    module name. `npx <tool> ...` is the one form without a leading flag that is kept.

Without --list the output is one line: every rule in single quotes, separated by
spaces, ready to paste after --allowedTools. With --list it is one raw rule per line.

A missing project.json, or a missing or null "commands", gives only the git rules.
Invalid JSON prints a message to stderr and exits 1.

The script never prints Edit, Write, a bare Bash or Bash(*). File edits are covered by
--permission-mode acceptEdits, which the caller passes separately.

Python 3.8+, standard library only.
"""

import argparse
import json
import re
import shlex
import sys
from pathlib import Path

GIT_ENTRIES = (
    "git status",
    "git diff",
    "git log",
    "git show",
    "git rev-parse",
)

# A word containing any of these ends the prefix: it is a variable, a glob, a quote,
# a subshell, a redirect or an escape, so the real argument is not known in advance.
BAD_CHARS = frozenset("$*?\"'(){}<>`\\")

# Words that only introduce a command: drop them and keep the rest of the command.
WRAPPER_WORDS = frozenset({"do", "then", "else", "elif", "if", "while", "until", "!", "{"})

# Words that start something that is not a check command: the whole simple command is ignored.
IGNORED_WORDS = frozenset({
    "for", "case", "select", "done", "fi", "esac", "in", "exit", "cd",
    "true", "false", ":", "return", "break", "continue",
})

# Commands that run whatever is piped or passed into them: no rule after a pipe.
PIPE_SINKS = frozenset({"tee", "xargs", "sponge"})

# Interpreters and shells: a rule for one of these must name a flag or tool, never a script.
INTERPRETERS = frozenset({"bash", "sh", "zsh", "python", "python3", "node", "ruby", "perl", "npx"})

# Interpreter options that run code given on the command line.
EVAL_FLAGS = frozenset({"-c", "-e", "-p", "--eval", "--print"})
FLAG_CLUSTER = re.compile(r"^-[A-Za-z]+$")

ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
TRAILING_NOTE = re.compile(r"\s+\([^\n]*\)\s*$")


def split_simple(text):
    """Split a command string into simple commands at &&, ||, ;, | and newlines.

    Return (command, after_pipe) pairs; after_pipe is true for a command that follows a
    single |.
    """
    text = TRAILING_NOTE.sub("", text)
    parts = []
    current = []
    piped = False
    quote = None
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if quote:
            current.append(c)
            if c == "\\" and quote == '"' and i + 1 < n:
                i += 1
                current.append(text[i])
            elif c == quote:
                quote = None
        elif c == "\\" and i + 1 < n:
            current.append(c)
            i += 1
            current.append(text[i])
        elif c in ("'", '"'):
            quote = c
            current.append(c)
        elif c in ";|\n":
            parts.append(("".join(current), piped))
            current = []
            piped = False
            if c == "|":
                if i + 1 < n and text[i + 1] == "|":
                    i += 1
                else:
                    piped = True
        elif c == "&" and i + 1 < n and text[i + 1] == "&":
            parts.append(("".join(current), piped))
            current = []
            piped = False
            i += 1
        else:
            current.append(c)
        i += 1
    parts.append(("".join(current), piped))
    return [(p.strip(), after) for p, after in parts if p.strip()]


def tokenize(simple):
    """Split a simple command into words, keeping quote characters inside the words."""
    lexer = shlex.shlex(simple, posix=False)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        return list(lexer)
    except ValueError:
        return simple.split()


def prefix_words(simple):
    """Return the leading words of a simple command that can go in a rule, or []."""
    words = tokenize(simple)
    while words and (ENV_ASSIGNMENT.match(words[0]) or words[0] in WRAPPER_WORDS):
        words = words[1:]
    if not words or words[0] in IGNORED_WORDS:
        return []
    prefix = []
    for word in words:
        if any(ch in BAD_CHARS for ch in word):
            break
        prefix.append(word)
    return prefix


def rule_allowed(words, after_pipe):
    """Return True when the prefix words may become a rule (see the module docstring)."""
    if after_pipe and words[0] in PIPE_SINKS:
        return False
    if words[0] not in INTERPRETERS:
        return True
    if words[0] == "npx":
        return len(words) > 1 and not words[1].startswith("-")
    if len(words) < 2 or not words[1].startswith("-"):
        return False
    # Check the interpreter's own options: everything up to and including -m. What
    # follows -m <module> belongs to the module, not to the interpreter.
    for word in words[1:]:
        if word.split("=")[0] in EVAL_FLAGS:
            return False
        if FLAG_CLUSTER.match(word) and ("c" in word or "e" in word):
            return False
        if word == "-m":
            break
    return words[-1] != "-m"


def check_commands(commands):
    """Yield every command string from the "commands" object of project.json."""
    for key in ("typecheck", "build", "test"):
        value = commands.get(key)
        if isinstance(value, str) and value.strip():
            yield value
    extra = commands.get("extraTests")
    if isinstance(extra, list):
        for item in extra:
            if isinstance(item, dict):
                value = item.get("command")
                if isinstance(value, str) and value.strip():
                    yield value


def entries_for(project_dir):
    """Return the rules for a project, git rules first. Raise ValueError on a bad file."""
    entries = ["Bash(%s:*)" % prefix for prefix in GIT_ENTRIES]
    path = Path(project_dir) / ".formic" / "project.json"
    if not path.is_file():
        return entries
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError("%s: cannot read: %s" % (path, exc))
    except json.JSONDecodeError as exc:
        raise ValueError("%s: invalid JSON: %s" % (path, exc))
    if not isinstance(data, dict):
        raise ValueError("%s: top level must be a JSON object" % path)
    commands = data.get("commands")
    if commands is None:
        return entries
    if not isinstance(commands, dict):
        raise ValueError('%s: "commands" must be an object or null' % path)
    for text in check_commands(commands):
        for simple, after_pipe in split_simple(text):
            words = prefix_words(simple)
            if words and rule_allowed(words, after_pipe):
                entry = "Bash(%s:*)" % " ".join(words)
                if entry not in entries:
                    entries.append(entry)
    return entries


def main():
    parser = argparse.ArgumentParser(
        description="Print the Claude Code --allowedTools list for a formic-kit project.")
    parser.add_argument("--project", default=".",
                        help="project root that holds .formic/project.json (default: current directory)")
    parser.add_argument("--list", action="store_true",
                        help="print one raw rule per line instead of one quoted line")
    args = parser.parse_args()
    try:
        entries = entries_for(args.project)
    except ValueError as exc:
        print("allowed_tools.py: %s" % exc, file=sys.stderr)
        return 1
    if args.list:
        print("\n".join(entries))
    else:
        print(" ".join("'%s'" % entry for entry in entries))
    return 0


if __name__ == "__main__":
    sys.exit(main())
