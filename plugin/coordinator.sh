#!/usr/bin/env bash
# Action: start a coordinator agent beside the focused pane, in the project the user is in.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

relink_if_moved
project="$(project_root "$(context_dir)")"
[ -n "$project" ] || { echo "could not tell which project the focused pane is in" >&2; exit 1; }
[ -f "$project/.formic/board.json" ] || { echo "no .formic/board.json in $project; run the init action first" >&2; exit 1; }

ws="${HERDR_WORKSPACE_ID:-w}"
name="coordinator-$(printf '%s' "$ws" | tr -c 'a-z0-9' '-' | sed 's/-*$//')"

# One coordinator per workspace: two would both write the board.
if "$HERDR" agent get "$name" >/dev/null 2>&1; then
  exec "$HERDR" agent focus "$name"
fi

pane="$("$HERDR" pane split ${HERDR_PANE_ID:+--pane "$HERDR_PANE_ID"} --direction right --cwd "$project" \
  | python3 -c 'import json, sys; print(json.load(sys.stdin)["result"]["pane"]["pane_id"])')"
sleep 1
case "$(saved_runtime)" in
  opencode)
    "$HERDR" agent start "$name" --kind opencode --pane "$pane" --timeout 120000 -- --agent formic-coordinator
    ;;
  claude)
    args=(--agent formic-coordinator)
    model="$(saved_setting claude_coordinator_model)"
    [ -z "$model" ] || args+=(--model "$model")
    out="$(mktemp)"
    status=0
    "$HERDR" agent start "$name" --kind claude --pane "$pane" --timeout 120000 -- "${args[@]}" > "$out" 2>&1 || status=$?
    if [ "$status" -ne 0 ] || grep -qF agent_not_ready "$out"; then
      cat "$out" >&2
      rm -f "$out"
      {
        echo
        echo "Claude Code did not become ready in the new pane. It may be showing a question,"
        echo "such as whether you trust this folder. Look at the new pane, answer it there"
        echo "yourself, then run this action again."
      } >&2
      exit 1
    fi
    cat "$out"
    rm -f "$out"
    ;;
  *)
    echo "unknown runtime '$(saved_runtime)' in the formic-kit settings; run the setup action" >&2
    exit 1
    ;;
esac
