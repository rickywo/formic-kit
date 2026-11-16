#!/usr/bin/env bash
# Pane: live read-only view of the project's task board.
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

project="${FORMIC_PROJECT:-}"
if [ -z "$project" ] || [ ! -f "$project/.formic/board.json" ]; then
  echo "No task board found${project:+ in $project}."
  echo "Run the action \"Formic: set up the board in this project\" first."
  pause; exit 1
fi
exec python3 "$KIT_DIR/plugin/board_view.py" "$project"
