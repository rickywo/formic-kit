#!/usr/bin/env bash
# Send a brief to a formic-kit worker and wait for it to stop, checking that the brief
# actually arrived.
#
# Usage: send_brief.sh <agent-name> <brief-file> <timeout-ms>
#
# Prints one line of JSON:
#   {"delivered": true,  "status": "<idle|done|blocked|...>", "sessionId": "...", "herdr": {...}}
#   {"delivered": false, "reason": "...", "herdr": {...}}
# Exit codes: 0 the worker stopped (read the status), 3 the brief was not delivered,
# 1 usage or herdr error.
#
# Why: a brief can be lost without herdr noticing. The worker then sits idle with no
# session while `herdr agent prompt --wait` keeps waiting. A worker gets a session as
# soon as it receives its first message, so no session after DELIVERY_SECONDS means the
# brief did not arrive.

set -u

NAME="${1:-}"; BRIEF="${2:-}"; TIMEOUT_MS="${3:-}"
DELIVERY_SECONDS="${FORMIC_DELIVERY_SECONDS:-60}"
HERDR="${HERDR_BIN_PATH:-herdr}"

if [ -z "$NAME" ] || [ ! -f "$BRIEF" ] || [ -z "$TIMEOUT_MS" ]; then
  echo "usage: send_brief.sh <agent-name> <brief-file> <timeout-ms>" >&2
  exit 1
fi

out="$(mktemp)"
pid=""
cleanup() {
  [ -n "$pid" ] && kill "$pid" 2>/dev/null
  rm -f "$out"
}
trap cleanup EXIT

session_of() {
  "$HERDR" agent get "$NAME" 2>/dev/null | python3 -c '
import json, sys
try:
    a = json.load(sys.stdin)["result"]["agent"]
except (ValueError, KeyError, TypeError):
    sys.exit(0)
print((a.get("agent_session") or {}).get("value") or "")'
}

json_or_null() {
  python3 -c '
import json, sys
raw = open(sys.argv[1]).read().strip()
try:
    print(json.dumps(json.loads(raw)))
except ValueError:
    print(json.dumps({"raw": raw[-1000:]}))' "$out"
}

"$HERDR" agent prompt "$NAME" "$(cat "$BRIEF")" --wait --timeout "$TIMEOUT_MS" > "$out" 2>&1 &
pid=$!

session=""
waited=0
while [ "$waited" -lt "$DELIVERY_SECONDS" ]; do
  sleep 5
  waited=$((waited + 5))
  session="$(session_of)"
  [ -n "$session" ] && break
  kill -0 "$pid" 2>/dev/null || break
done

if [ -z "$session" ]; then
  session="$(session_of)"
fi

if [ -z "$session" ]; then
  kill "$pid" 2>/dev/null
  wait "$pid" 2>/dev/null
  pid=""
  printf '{"delivered": false, "reason": "the worker has no session %ss after the brief was sent, so the brief did not arrive", "herdr": %s}\n' \
    "$waited" "$(json_or_null)"
  exit 3
fi

wait "$pid"
pid=""
python3 - "$out" "$session" <<'PY'
import json, sys
raw = open(sys.argv[1]).read().strip()
try:
    h = json.loads(raw)
except ValueError:
    h = {"raw": raw[-1000:]}
status = ((h.get("result") or {}).get("agent") or {}).get("agent_status") \
    or (h.get("error") or {}).get("code") or "unknown"
print(json.dumps({"delivered": True, "status": status, "sessionId": sys.argv[2], "herdr": h}))
PY
