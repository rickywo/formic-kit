#!/usr/bin/env bash
# Pane: ask for the runtime and the three model ids, then run the installer and the doctor.
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

ask() {
  local label="$1" current="$2" answer
  if [ -n "$current" ]; then printf '%s [%s]: ' "$label" "$current" >&2
  else printf '%s: ' "$label" >&2; fi
  read -r answer || answer=""
  printf '%s\n' "${answer:-$current}"
}

echo "Formic Kit setup"
echo
echo "The kit can run on opencode or on Claude Code. One tool runs the coordinator and the workers."
echo "Press Enter to keep the value in brackets."
echo

runtime=""
tries=0
while [ -z "$runtime" ]; do
  answer="$(ask "Runtime (opencode or claude)" "$(saved_runtime)")"
  case "$answer" in
    opencode|claude) runtime="$answer" ;;
    *)
      tries=$((tries + 1))
      echo "'$answer' is not a runtime. Type opencode or claude."
      if [ "$tries" -ge 3 ]; then
        echo "Setup stopped: no valid runtime. Run the setup action again."
        pause; exit 1
      fi
      ;;
  esac
done

echo
if [ "$runtime" = "claude" ]; then
  echo "This links the kit's skills into ~/.claude/skills and writes four agent files"
  echo "into ~/.claude/agents: formic-coordinator, formic-ops, worker-sonnet, worker-haiku."
  echo "Claude Code model ids have no provider prefix (the ids 'claude --model' accepts)."
  echo "Workers need the mid-tier and low-cost ids; the coordinator id is optional."
  coordinator_key=claude_coordinator_model; sonnet_key=claude_sonnet_model; haiku_key=claude_haiku_model
else
  echo "This links the kit's skills into ~/.config/opencode/skills and writes four agent"
  echo "profiles into ~/.config/opencode/agents: formic-coordinator, formic-ops, worker-sonnet, worker-haiku."
  echo "Model ids use opencode's provider/model form. 'opencode models' lists them."
  coordinator_key=coordinator_model; sonnet_key=sonnet_model; haiku_key=haiku_model
fi
echo

coordinator="$(ask "Coordinator model (your strongest)" "$(saved_setting "$coordinator_key")")"
sonnet="$(ask "Mid-tier worker model" "$(saved_setting "$sonnet_key")")"
haiku="$(ask "Low-cost worker model" "$(saved_setting "$haiku_key")")"

args=(--runtime "$runtime")
[ -n "$coordinator" ] && args+=(--coordinator-model "$coordinator")
[ -n "$sonnet" ] && args+=(--sonnet-model "$sonnet")
[ -n "$haiku" ] && args+=(--haiku-model "$haiku")

echo
if bash "$KIT_DIR/install.sh" install ${args[@]+"${args[@]}"}; then
  echo
  bash "$KIT_DIR/install.sh" doctor ${FORMIC_PROJECT:+"$FORMIC_PROJECT"} || true
fi
pause
