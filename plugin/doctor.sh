#!/usr/bin/env bash
# Pane: run the doctor for this machine and the project the user is in.
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

project="${FORMIC_PROJECT:-}"
if [ -n "$project" ] && [ -d "$project/.formic" ]; then
  bash "$KIT_DIR/install.sh" doctor "$project"
else
  bash "$KIT_DIR/install.sh" doctor
fi
pause
