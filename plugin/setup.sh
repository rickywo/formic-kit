#!/usr/bin/env bash
# Pane: ask for the three model ids, then run the installer and the doctor.
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

state="${FORMIC_KIT_STATE_DIR:-$HOME/.config/formic-kit}/config"
saved() { [ -f "$state" ] && awk -F= -v k="$1" '$1 == k { print substr($0, length(k) + 2) }' "$state"; }

ask() {
  local label="$1" current="$2" answer
  if [ -n "$current" ]; then printf '%s [%s]: ' "$label" "$current" >&2
  else printf '%s: ' "$label" >&2; fi
  read -r answer || answer=""
  printf '%s\n' "${answer:-$current}"
}

echo "Formic Kit setup"
echo
echo "This links the kit's skills into ~/.config/opencode/skills and writes three agent"
echo "profiles into ~/.config/opencode/agents: formic-coordinator, worker-sonnet, worker-haiku."
echo "Model ids use opencode's provider/model form. 'opencode models' lists them."
echo "Press Enter to keep the value in brackets."
echo

coordinator="$(ask "Coordinator model (your strongest)" "$(saved coordinator_model)")"
sonnet="$(ask "Mid-tier worker model" "$(saved sonnet_model)")"
haiku="$(ask "Low-cost worker model" "$(saved haiku_model)")"

args=()
[ -n "$coordinator" ] && args+=(--coordinator-model "$coordinator")
[ -n "$sonnet" ] && args+=(--sonnet-model "$sonnet")
[ -n "$haiku" ] && args+=(--haiku-model "$haiku")

echo
if bash "$KIT_DIR/install.sh" install ${args[@]+"${args[@]}"}; then
  echo
  bash "$KIT_DIR/install.sh" doctor ${FORMIC_PROJECT:+"$FORMIC_PROJECT"} || true
fi
pause
