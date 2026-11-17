#!/usr/bin/env bash
# Send a brief to a formic-kit worker and wait for it to stop, checking that the brief
# actually arrived.
#
# Usage: send_brief.sh <agent-name> <brief-file> <timeout-ms>
#
# Prints one line of JSON:
#   {"delivered": true,  "status": "<idle|done|blocked|...>", "sessionId": "...", "herdr": {...}}
#   {"delivered": false, "reason": "...", "herdr": {...}}
#   When the worker is still `working` after the wait (or herdr says `timeout`), the
#   status is "timeout" and the agent's own state is in a separate "agentStatus" key.
# Exit codes: 0 the worker stopped or the wait ran out (read the status), 3 the brief
# was not delivered, 1 usage or herdr error.
#
# Why: a brief can be lost without herdr noticing. The tool is read from
# `herdr agent get`: `agent_session.agent` equal to `claude` means Claude Code, anything
# else (including no session yet) means opencode.
#
# opencode: a worker gets a session as soon as it receives its first message, so no
# session after DELIVERY_SECONDS means the brief did not arrive.
#
# Claude Code: the worker has a session from the moment it starts, so that rule cannot
# work. The brief counts as delivered once the session transcript
# (<root>/projects/*/<session-id>.jsonl) has a `user` entry with the brief text (a string
# or a list of text parts; entries marked isMeta are ignored; whitespace is collapsed).
# <root> is FORMIC_CLAUDE_DIR if set, else CLAUDE_CONFIG_DIR if set, else ~/.claude. This
# is where Claude Code writes transcripts, not necessarily the folder the kit installed
# into. If the brief is missing after half of DELIVERY_SECONDS, then on every poll
# afterwards the pane is checked: when herdr reports the agent `idle`, no dialog is
# showing, and the brief (or a "[Pasted text" placeholder) is in the input area after
# the last prompt line, Enter is pressed, once (the only key this script ever sends). If
# the transcript still has no brief when the window ends, the brief was not delivered.
# No dialog is ever answered.
#
# Environment: HERDR_BIN_PATH (herdr binary), FORMIC_DELIVERY_SECONDS (default 60) and
# FORMIC_POLL_SECONDS (default 5) are both whole numbers of seconds; FORMIC_CLAUDE_DIR
# and CLAUDE_CONFIG_DIR choose the Claude Code folder as described above.

set -u

NAME="${1:-}"; BRIEF="${2:-}"; TIMEOUT_MS="${3:-}"
DELIVERY_SECONDS="${FORMIC_DELIVERY_SECONDS:-60}"
POLL_SECONDS="${FORMIC_POLL_SECONDS:-5}"
HERDR="${HERDR_BIN_PATH:-herdr}"

if [ -z "$NAME" ] || [ ! -f "$BRIEF" ] || [ -z "$TIMEOUT_MS" ]; then
  echo "usage: send_brief.sh <agent-name> <brief-file> <timeout-ms>" >&2
  exit 1
fi

out="$(mktemp)"
pane="$(mktemp)"
waitout="$(mktemp)"
pid=""
start=$SECONDS
cleanup() {
  [ -n "$pid" ] && kill "$pid" 2>/dev/null
  rm -f "$out" "$pane" "$waitout"
}
trap cleanup EXIT

# Prints "<tool>:<session>" (tool is claude or opencode, session may be empty), or
# nothing when `herdr agent get` fails or does not print JSON.
agent_info() {
  "$HERDR" agent get "$NAME" 2>/dev/null | python3 -c '
import json, sys
try:
    a = json.load(sys.stdin)["result"]["agent"]
except (ValueError, KeyError, TypeError):
    sys.exit(0)
s = a.get("agent_session") or {}
print(("claude" if s.get("agent") == "claude" else "opencode") + ":" + (s.get("value") or ""))'
}

# Prints result.agent.agent_status from `herdr agent get`, or nothing.
status_of() {
  "$HERDR" agent get "$NAME" 2>/dev/null | python3 -c '
import json, sys
try:
    a = json.load(sys.stdin)["result"]["agent"]
except (ValueError, KeyError, TypeError):
    sys.exit(0)
print(a.get("agent_status") or "")'
}

# Exit 0 when the transcript of session $1 has a `user` entry with the brief, either as
# the whole entry or inside one Claude Code <pasted_content id="..."> envelope.
# The transcript lookup and the user-entry parsing must stay in step with find_transcript
# and user_text in worker_report.py.
brief_delivered() {
  python3 - "$1" "$BRIEF" <<'PY'
import glob, json, os, re, sys
sess, brief_file = sys.argv[1], sys.argv[2]
brief = " ".join(open(brief_file, encoding="utf-8", errors="replace").read().split())
root = (os.environ.get("FORMIC_CLAUDE_DIR") or os.environ.get("CLAUDE_CONFIG_DIR")
        or os.path.expanduser("~/.claude"))
matches = glob.glob(os.path.join(root, "projects", "*", glob.escape(sess) + ".jsonl"))
if not brief or not matches:
    sys.exit(1)
path = max(matches, key=os.path.getmtime)
prefix = brief[:200]
with open(path, encoding="utf-8", errors="replace") as f:
    for line in f:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if not isinstance(e, dict) or e.get("type") != "user" or e.get("isMeta") is True:
            continue
        msg = e.get("message")
        content = msg.get("content") if isinstance(msg, dict) else None
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            parts = [p.get("text") for p in content
                     if isinstance(p, dict) and p.get("type") == "text"]
            text = " ".join(t for t in parts if isinstance(t, str))
        else:
            continue
        # Claude Code stores a pasted prompt as <pasted_content id="X">...</pasted_content id="X">.
        # Compare only the inner text, and only when the whole entry is one such envelope.
        m = re.fullmatch(r'\s*<pasted_content id="([^"]+)">(.*)</pasted_content id="\1">\s*',
                         text, re.S)
        if m:
            text = m.group(2)
        text = " ".join(text.split())
        if text and (text == brief or text.startswith(prefix)):
            sys.exit(0)
sys.exit(1)
PY
}

# Exit 0 when the brief is waiting, unsubmitted, in the input box of an idle agent:
#   - herdr reports the agent `idle` (not working, not blocked);
#   - the pane shows no dialog (Esc to cancel, Do you want/trust, Enter to confirm, or
#     numbered Yes/No options);
#   - the text from the last prompt line (the line with the prompt character) to the end
#     of the pane holds a distinctive line of the brief, or a "[Pasted text" placeholder.
# The pane hard-wraps long lines, so all whitespace is removed before comparing.
input_has_brief() {
  [ "$(status_of)" = "idle" ] || return 1
  "$HERDR" agent read "$NAME" --source visible --lines 45 > "$pane" 2>/dev/null
  python3 - "$BRIEF" "$pane" <<'PY'
import json, re, sys
brief = open(sys.argv[1], encoding="utf-8", errors="replace").read()
lines = [l.strip() for l in brief.splitlines() if l.strip()]
snippet = ""
for l in lines:
    if l.startswith("- Task folder:") or l.startswith("Task folder:"):
        snippet = l[2:].strip() if l.startswith("- ") else l
        break
if not snippet and lines:
    snippet = max(lines, key=len)[:80]
raw = open(sys.argv[2], encoding="utf-8", errors="replace").read()
try:
    parts = []
    def walk(v):
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(json.loads(raw))
    pane = "\n".join(parts)
except ValueError:
    pane = raw
dialog = re.compile(
    r"Esc to cancel|Do you (want|trust)|Enter to confirm|^\s*(\u276f\s*)?[0-9]+\.\s+(Yes|No)\b",
    re.M)
if dialog.search(pane):
    sys.exit(1)
rows = pane.split("\n")
last = max((i for i, r in enumerate(rows) if "\u276f" in r), default=None)
if last is None:
    sys.exit(1)
squash = lambda t: re.sub(r"\s+", "", t)
tail = squash("\n".join(rows[last:]))
found = (snippet and squash(snippet) in tail) or "[Pastedtext" in tail
sys.exit(0 if found else 1)
PY
}

# Prints the JSON in file $1 (default: the prompt output), or {"raw": ...} when it is not JSON.
json_or_null() {
  python3 -c '
import json, sys
raw = open(sys.argv[1]).read().strip()
try:
    print(json.dumps(json.loads(raw)))
except ValueError:
    print(json.dumps({"raw": raw[-1000:]}))' "${1:-$out}"
}

# Exit 0 when the prompt output in $out is JSON with an "error" key.
prompt_errored() {
  python3 -c '
import json, sys
try:
    h = json.loads(open(sys.argv[1]).read().strip())
except ValueError:
    sys.exit(0)
sys.exit(0 if isinstance(h, dict) and h.get("error") else 1)' "$out"
}

"$HERDR" agent prompt "$NAME" "$(cat "$BRIEF")" --wait --timeout "$TIMEOUT_MS" > "$out" 2>&1 &
pid=$!

tool="opencode"
session=""
waited=0
nudged=0
delivered=0
half=$((DELIVERY_SECONDS / 2))

# Reads agent_info into tool and session. A failed `agent get` changes nothing, claude
# is never switched back, and an empty session never replaces a known one.
refresh() {
  local info s
  info="$(agent_info)"
  [ -n "$info" ] || return 0
  [ "${info%%:*}" = "claude" ] && tool="claude"
  s="${info#*:}"
  [ -n "$s" ] && session="$s"
  return 0
}

while [ "$waited" -lt "$DELIVERY_SECONDS" ]; do
  sleep "$POLL_SECONDS"
  waited=$((waited + POLL_SECONDS))
  refresh
  if [ "$tool" = "claude" ]; then
    if [ -n "$session" ] && brief_delivered "$session"; then
      delivered=1
      break
    fi
    if [ "$nudged" -eq 0 ] && [ "$waited" -ge "$half" ]; then
      # The brief may sit unsubmitted in the input box. Press Enter once, and only when
      # the agent is idle, no dialog shows and the brief is in the input area. Check
      # again on every poll until Enter has been sent. This is the only key this script
      # ever sends.
      if input_has_brief; then
        nudged=1
        "$HERDR" agent send-keys "$NAME" enter >/dev/null 2>&1
      fi
    fi
  else
    [ -n "$session" ] && break
    kill -0 "$pid" 2>/dev/null || break
  fi
done

if [ "$tool" != "claude" ] && [ -z "$session" ]; then
  refresh
fi

if [ "$tool" = "claude" ]; then
  if [ "$delivered" -eq 0 ] && [ -n "$session" ] && brief_delivered "$session"; then
    delivered=1
  fi
  if [ "$delivered" -eq 0 ]; then
    kill "$pid" 2>/dev/null
    wait "$pid" 2>/dev/null
    pid=""
    printf '{"delivered": false, "reason": "Claude Code never recorded the brief in its transcript within %ss", "herdr": %s}\n' \
      "$waited" "$(json_or_null)"
    exit 3
  fi
elif [ -z "$session" ]; then
  kill "$pid" 2>/dev/null
  wait "$pid" 2>/dev/null
  pid=""
  printf '{"delivered": false, "reason": "the worker has no session %ss after the brief was sent, so the brief did not arrive", "herdr": %s}\n' \
    "$waited" "$(json_or_null)"
  exit 3
fi

# A Claude Code prompt that stalled before the brief was submitted has already exited
# with an error. The worker is still running, so wait for it with `agent wait`.
status_override=""
herdr_file="$out"
if [ "$tool" = "claude" ] && ! kill -0 "$pid" 2>/dev/null; then
  wait "$pid" 2>/dev/null
  pid=""
  if prompt_errored; then
    remaining=$((TIMEOUT_MS - (SECONDS - start) * 1000))
    [ "$remaining" -ge 1000 ] || remaining=1000
    "$HERDR" agent wait "$NAME" --timeout "$remaining" > "$waitout" 2>&1
    status_override="$(status_of)"
    herdr_file="$waitout"
  fi
else
  wait "$pid"
  pid=""
fi

agent_state="$(status_of)"

python3 - "$herdr_file" "$session" "$status_override" "$agent_state" <<'PY'
import json, sys
raw = open(sys.argv[1]).read().strip()
try:
    h = json.loads(raw)
except ValueError:
    h = {"raw": raw[-1000:]}
if not isinstance(h, dict):
    h = {"raw": raw[-1000:]}
status = sys.argv[3] or ((h.get("result") or {}).get("agent") or {}).get("agent_status") \
    or (h.get("error") or {}).get("code") or "unknown"
result = {"delivered": True, "status": status, "sessionId": sys.argv[2], "herdr": h}
if status in ("working", "timeout"):
    # The wait ran out while the worker was still going. Report that as a timeout and
    # keep the agent's own state apart.
    result["status"] = "timeout"
    result["agentStatus"] = sys.argv[4] \
        or ((h.get("result") or {}).get("agent") or {}).get("agent_status") or ""
print(json.dumps(result))
PY
