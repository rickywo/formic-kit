#!/usr/bin/env python3
"""Print a formic-kit worker's final message, read from its opencode session.

Usage: worker_report.py <herdr-agent-name-or-pane-id>
       worker_report.py --session <opencode-session-id>

Reads the session through `opencode export`, which returns the message exactly
as written. Reading the terminal instead would give text wrapped at the pane
width. Python 3.8+, standard library only.

verdict is the first word of the final message (DONE, PARTIAL, BLOCKED, FAILED), or:
  NONE           the message did not start with one of those words
  ERROR          the turn ended with an error instead of a message; see "error" and
                 "errorKind" ("credentials" means the model provider rejected the sign-in)
  NOT_DELIVERED  the worker has no session, so it never received its brief
"""

import json
import re
import subprocess
import sys
import tempfile


CREDENTIAL_PATTERNS = re.compile(
    r"security token included in the request is (expired|invalid)"
    r"|ExpiredToken|credential provider failed|Could not load credentials"
    r"|UnrecognizedClient|InvalidClientTokenId|token has expired|SSO session",
    re.IGNORECASE,
)


def fail(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def session_for(target):
    r = subprocess.run(["herdr", "agent", "get", target], capture_output=True, text=True)
    if r.returncode != 0:
        fail(f"herdr agent get {target} failed: {r.stderr.strip() or r.stdout.strip()}")
    agent = json.loads(r.stdout)["result"]["agent"]
    sess = (agent.get("agent_session") or {}).get("value")
    return sess, agent.get("agent_status")


def main():
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == "--session":
        sess, status = args[1], None
    elif len(args) == 1:
        sess, status = session_for(args[0])
        if not sess:
            print(json.dumps({
                "sessionId": None,
                "agentStatus": status,
                "verdict": "NOT_DELIVERED",
                "message": "the worker has no session: it never received a brief",
            }, indent=2))
            return
    else:
        fail("usage: worker_report.py <agent-name> | --session <session-id>")

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
