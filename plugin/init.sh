#!/usr/bin/env bash
# Pane: set up the board in the project the user is in.
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

project="${FORMIC_PROJECT:-}"
if [ -z "$project" ] || [ ! -d "$project" ]; then
  echo "Could not tell which project you are in. Run this from a pane inside the project."
  pause; exit 1
fi

echo "Set up a formic-kit board in:"
echo "  $project"
echo
echo "This creates .formic/board.json and .formic/project.json if they are absent and"
echo "adds a short section to AGENTS.md. An existing board is never changed."
if [ "$(saved_runtime)" = "claude" ]; then
  echo "Claude Code reads CLAUDE.md, not AGENTS.md, so this also creates a CLAUDE.md"
  echo "containing @AGENTS.md if the project has none. An existing CLAUDE.md is left alone."
fi
printf '\nContinue? [y/N] '
read -r answer || answer=""
case "$answer" in
  y|Y|yes) echo; bash "$KIT_DIR/install.sh" init "$project" ;;
  *) echo "Nothing was changed." ;;
esac
pause
