#!/usr/bin/env bash
# Action wrapper: open one of the plugin's panes for the project the user is in.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

entry="${1:?usage: open.sh <setup|init|doctor|board>}"
project="$(project_root "$(context_dir)")"
exec "$HERDR" plugin pane open --plugin "${HERDR_PLUGIN_ID:-formic.kit}" --entrypoint "$entry" \
  --env "FORMIC_PROJECT=$project"
