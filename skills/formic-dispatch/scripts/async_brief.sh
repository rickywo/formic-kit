#!/usr/bin/env bash
# Run send_brief.sh in the background and wait for it in short steps, so that no single
# shell command runs longer than 9 minutes (the Claude Code Bash tool stops a command
# after at most 10 minutes).
#
# Usage:
#   async_brief.sh start <agent-name> <brief-file> <timeout-ms> <result-file>
#   async_brief.sh wait  <result-file> [seconds]
#
# start: runs send_brief.sh (found next to this script) detached with nohup, then prints
#   `started` and returns at once. send_brief.sh stdout goes to <result-file>.part, stderr
#   to <result-file>.err. When send_brief.sh exits, its exit code is written to
#   <result-file>.code and then <result-file>.part is renamed to <result-file>. The .code
#   file comes last, so its presence means the run has finished. The wrapper's pid is in
#   <result-file>.pid. start refuses to run (exit 1) while that pid is alive. The overall
#   limit is <timeout-ms>, enforced by send_brief.sh.
#
# wait: polls every FORMIC_ASYNC_POLL_SECONDS (default 5, whole seconds) for up to
#   [seconds] (default 480, at most 540). When the run has finished it prints the
#   contents of <result-file> and exits with the exit code of send_brief.sh (0 the worker
#   stopped, 3 the brief was not delivered, 1 usage or herdr error). When the time is up
#   it prints the single line `still running` and exits 0: a normal wait is not an
#   error, so tell the two apart by the output (`still running` or a line of JSON).
#   If the background run died without leaving an exit code, it prints a JSON line with
#   "delivered": false and the tail of the error file, and exits 1.

set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
POLL="${FORMIC_ASYNC_POLL_SECONDS:-5}"
MAX_WAIT=540

usage() {
  echo "usage: async_brief.sh start <agent-name> <brief-file> <timeout-ms> <result-file>" >&2
  echo "       async_brief.sh wait <result-file> [seconds]" >&2
  exit 1
}

alive() {
  [ -n "${1:-}" ] && kill -0 "$1" 2>/dev/null
}

cmd_start() {
  local name="${1:-}" brief="${2:-}" timeout_ms="${3:-}" result="${4:-}"
  if [ -z "$name" ] || [ ! -f "$brief" ] || [ -z "$timeout_ms" ] || [ -z "$result" ]; then
    usage
  fi
  if [ -f "$result.pid" ] && alive "$(cat "$result.pid" 2>/dev/null)"; then
    echo "error: a run for $result is still going (pid $(cat "$result.pid"))" >&2
    exit 1
  fi
  rm -f "$result" "$result.part" "$result.err" "$result.code" "$result.pid"
  mkdir -p "$(dirname "$result")"
  nohup bash -c '
    here="$1"; name="$2"; brief="$3"; timeout_ms="$4"; result="$5"
    bash "$here/send_brief.sh" "$name" "$brief" "$timeout_ms" > "$result.part" 2> "$result.err"
    code=$?
    echo "$code" > "$result.code.tmp"
    mv "$result.part" "$result"
    mv "$result.code.tmp" "$result.code"
  ' formic-async "$HERE" "$name" "$brief" "$timeout_ms" "$result" \
    > /dev/null 2>&1 < /dev/null &
  echo "$!" > "$result.pid"
  echo "started"
}

cmd_wait() {
  local result="${1:-}" seconds="${2:-480}" elapsed=0 pid code
  [ -n "$result" ] || usage
  case "$seconds" in
    ''|*[!0-9]*) usage ;;
  esac
  case "$POLL" in
    ''|*[!0-9]*|0) POLL=5 ;;
  esac
  [ "$seconds" -le "$MAX_WAIT" ] || seconds="$MAX_WAIT"
  while :; do
    if [ -f "$result.code" ]; then
      code="$(cat "$result.code")"
      cat "$result"
      case "$code" in
        ''|*[!0-9]*) code=1 ;;
      esac
      exit "$code"
    fi
    pid="$(cat "$result.pid" 2>/dev/null || true)"
    if [ -z "$pid" ]; then
      echo "error: no run was started for $result" >&2
      exit 1
    fi
    if ! alive "$pid" && [ ! -f "$result.code" ]; then
      python3 -c '
import json, sys
try:
    tail = open(sys.argv[1], errors="replace").read()[-1000:]
except OSError:
    tail = ""
print(json.dumps({"delivered": False,
                  "reason": "send_brief.sh stopped without a result",
                  "stderr": tail}))' "$result.err"
      exit 1
    fi
    if [ "$elapsed" -ge "$seconds" ]; then
      echo "still running"
      exit 0
    fi
    sleep "$POLL"
    elapsed=$((elapsed + POLL))
  done
}

case "${1:-}" in
  start) shift; cmd_start "$@" ;;
  wait) shift; cmd_wait "$@" ;;
  *) usage ;;
esac
