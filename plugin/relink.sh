#!/usr/bin/env bash
# Startup hook: after a plugin install or update the kit lives in a new folder, so point
# the skill links and agent profiles at it again. Does nothing before the first setup.
# The same check also runs at the start of every plugin action.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

state="${FORMIC_KIT_STATE_DIR:-$HOME/.config/formic-kit}/config"
[ -f "$state" ] || { echo "formic-kit: not set up yet; run the setup action"; exit 0; }
relink_if_moved
