#!/usr/bin/env python3
"""Print a formic-kit worker's final message, read from its session.

Usage: worker_report.py <herdr-agent-name-or-pane-id>
       worker_report.py --session <session-id> [--tool opencode|claude]

The tool (opencode or claude) is taken from `herdr agent get`
(result.agent.agent_session.agent); a missing value means opencode. With --session
there is no herdr lookup, so --tool says which tool owns the session; the default is
opencode. The herdr binary is $HERDR_BIN_PATH, or `herdr` when that is not set.

opencode: reads the session through `opencode export`, which returns the message
exactly as written. Reading the terminal instead would give text wrapped at the pane
width.

claude: reads the session transcript, a JSON Lines file found with the glob
<root>/projects/*/<session-id>.jsonl. <root> is $FORMIC_CLAUDE_DIR if set, else
$CLAUDE_CONFIG_DIR if set, else ~/.claude. It is where Claude Code writes its
transcripts, which is not always the folder the kit installed into (--claude-dir). The
newest match wins. Claude Code has a session id from the moment it starts, so the
transcript is the delivery signal: no transcript file, or no user prompt in it, means
the brief never arrived. A user prompt is a `user` entry that is not marked `isMeta` and
has text, either as a string or as a list of text parts.

Python 3.8+, standard library only.

verdict is the first word of the final message (DONE, PARTIAL, BLOCKED, FAILED), or:
  NONE           the message did not start with one of those words
  ERROR          the turn ended with an error instead of a message; see "error" and
                 "errorKind" ("credentials" means the model provider rejected the sign-in)
  NOT_DELIVERED  the worker never received its brief (no session, or for claude no
                 transcript with a prompt)
"""

import glob
import json
import os
import re
import subprocess
import sys
import tempfile


CREDENTIAL_PATTERNS = re.compile(
    r"security token included in the request is (expired|invalid)"
    r"|ExpiredToken|credential provider failed|Could not load credentials"
    r"|UnrecognizedClient|InvalidClientTokenId|token has expired|SSO session"
    r"|Unable to locate credentials|AccessDenied[\s\S]{0,200}security token"
    r"|Missing (AWS )?credentials|aws sso login"
    r"|SSO (session|token)[\s\S]{0,40}(expired|invalid|missing)"
    r"|Token has expired and refresh failed"
    r"|invalid api key|please run /login|authentication[_ ]failed",
    re.IGNORECASE,
)

NO_MESSAGE = "(the last turn ended with no final message)"
VERDICTS = ("DONE", "PARTIAL", "BLOCKED", "FAILED")
USAGE = "usage: worker_report.py <agent-name> | --session <session-id> [--tool opencode|claude]"


def fail(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def session_for(target):
    herdr = os.environ.get("HERDR_BIN_PATH") or "herdr"
    r = subprocess.run([herdr, "agent", "get", target], capture_output=True, text=True)
    if r.returncode != 0:
        fail(f"herdr agent get {target} failed: {r.stderr.strip() or r.stdout.strip()}")
    agent = json.loads(r.stdout)["result"]["agent"]
    session = agent.get("agent_session") or {}
    tool = "claude" if session.get("agent") == "claude" else "opencode"
    return session.get("value"), agent.get("agent_status"), tool


def not_delivered(sess, status):
    print(json.dumps({
        "sessionId": sess,
        "agentStatus": status,
        "verdict": "NOT_DELIVERED",
        "message": "the worker has no session: it never received a brief",
    }, indent=2))


def parse_args(args):
    """Return (target, session, tool); exactly one of target and session is set."""
    if len(args) == 1 and not args[0].startswith("--"):
        return args[0], None, None
    session, tool, i = None, None, 0
    while i < len(args):
        if args[i] == "--session" and session is None and i + 1 < len(args):
            session, i = args[i + 1], i + 2
        elif args[i] == "--tool" and tool is None and i + 1 < len(args):
            tool, i = args[i + 1], i + 2
        else:
            fail(USAGE)
    if session is None or tool not in (None, "opencode", "claude"):
        fail(USAGE)
    return None, session, tool or "opencode"


def main():
    target, sess, tool = parse_args(sys.argv[1:])
    status = None
    if target is not None:
        sess, status, tool = session_for(target)
        if not sess:
            not_delivered(None, status)
            return
    if tool == "claude":
        report_claude(sess, status)
    else:
        report_opencode(sess, status)


def find_transcript(sess):
    root = (os.environ.get("FORMIC_CLAUDE_DIR") or os.environ.get("CLAUDE_CONFIG_DIR")
            or os.path.expanduser("~/.claude"))
    matches = glob.glob(os.path.join(root, "projects", "*", glob.escape(sess) + ".jsonl"))
    return max(matches, key=os.path.getmtime) if matches else None


def read_transcript(path):
    entries = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if isinstance(entry, dict):
                entries.append(entry)
    return entries


def message_of(entry):
    msg = entry.get("message")
    return msg if isinstance(msg, dict) else {}


def assistant_text(entry):
    content = message_of(entry).get("content")
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts = [p.get("text") for p in content if isinstance(p, dict) and p.get("type") == "text"]
    return "\n".join(t for t in parts if isinstance(t, str)).strip()


def user_text(entry):
    """Return the text of a `user` entry with whitespace collapsed, or "".

    Meta entries (isMeta true) give "". Content is a string, or a list whose text parts
    are joined by a space. Tool results have no text part, so they give "".
    """
    if entry.get("type") != "user" or entry.get("isMeta") is True:
        return ""
    content = message_of(entry).get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts = [p.get("text") for p in content if isinstance(p, dict) and p.get("type") == "text"]
        text = " ".join(t for t in parts if isinstance(t, str))
    else:
        return ""
    return " ".join(text.split())


def is_error_entry(entry):
    """True for an assistant entry that carries an API error instead of a message."""
    return bool(entry.get("isApiErrorMessage")) or entry.get("error") == "authentication_failed"


def report_claude(sess, status):
    path = find_transcript(sess)
    entries = read_transcript(path) if path else []
    if not any(user_text(e) for e in entries):
        not_delivered(sess, status)
        return

    assistants = [e for e in entries if e.get("type") == "assistant"]
    normal = [e for e in assistants if not is_error_entry(e)]
    with_text = [e for e in normal if assistant_text(e)]
    with_model = [e for e in normal if message_of(e).get("model")]
    settings = [e for e in entries if e.get("type") == "agent-setting"]

    err_msg, err_kind = None, None
    if assistants and is_error_entry(assistants[-1]):
        last = assistants[-1]
        err_msg = assistant_text(last)
        if not err_msg:
            err = last.get("error")
            err_msg = err if isinstance(err, str) else str(err)
        is_auth = last.get("error") == "authentication_failed"
        err_kind = "credentials" if is_auth or CREDENTIAL_PATTERNS.search(err_msg) else "other"

    text = assistant_text(with_text[-1]) if with_text and err_msg is None else ""
    words = text.split()
    verdict = words[0].strip("*:.,").upper() if words else ""
    if verdict not in VERDICTS:
        verdict = "NONE"
    if err_msg is not None:
        verdict = "ERROR"

    print(json.dumps({
        "sessionId": sess,
        "agentStatus": status,
        "agent": settings[-1].get("agentSetting") if settings else None,
        "model": message_of(with_model[-1]).get("model") if with_model else None,
        "verdict": verdict,
        "message": text or NO_MESSAGE,
        "error": err_msg,
        "errorKind": err_kind,
    }, indent=2))


def report_opencode(sess, status):
    # Export to a file, not a pipe: opencode truncates large exports written to a pipe.
    with tempfile.TemporaryFile("w+") as f:
        r = subprocess.run(["opencode", "export", sess], stdout=f, stderr=subprocess.PIPE, text=True)
        if r.returncode != 0:
            fail(f"opencode export {sess} failed: {r.stderr.strip()}")
        f.seek(0)
        out = f.read()
    try:
        data = json.loads(out[out.index("{"):])
    except ValueError as e:
        fail(f"could not parse the export of session {sess}: {e}")

    assistants = [m for m in data.get("messages", []) if m.get("info", {}).get("role") == "assistant"]
    if not assistants:
        fail(f"session {sess} has no assistant message")
    last = assistants[-1]
    info = last["info"]
    text = "\n".join(p.get("text", "") for p in last.get("parts", []) if p.get("type") == "text").strip()
    words = text.split()
    verdict = words[0].strip("*:.,").upper() if words else ""
    if verdict not in ("DONE", "PARTIAL", "BLOCKED", "FAILED"):
        verdict = "NONE"

    err = info.get("error") or {}
    err_msg = ((err.get("data") or {}).get("message") or err.get("name") or "") if err else ""
    err_kind = None
    if err_msg:
        err_kind = "credentials" if CREDENTIAL_PATTERNS.search(err_msg) else "other"
        if verdict == "NONE":
            verdict = "ERROR"

    print(json.dumps({
        "sessionId": sess,
        "agentStatus": status,
        "agent": info.get("agent"),
        "model": info.get("modelID"),
        "verdict": verdict,
        "message": text or "(the last turn ended with no final message)",
        "error": err_msg or None,
        "errorKind": err_kind,
    }, indent=2))


if __name__ == "__main__":
    main()
