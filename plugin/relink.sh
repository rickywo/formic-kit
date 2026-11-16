#!/usr/bin/env bash
# Startup hook: after a plugin install or update the kit lives in a new folder, so point
# the skill links and agent profiles at it again. Does nothing before the first setup.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

state="${FORMIC_KIT_STATE_DIR:-$HOME/.config/formic-kit}/config"
[ -f "$state" ] || { echo "formic-kit: not set up yet; run the setup action"; exit 0; }
recorded="$(awk -F= '$1 == "kit_dir" { print substr($0, 9) }' "$state")"
if [ "$recorded" = "$KIT_DIR" ]; then
  echo "formic-kit: links already point at $KIT_DIR"
  exit 0
fi
echo "formic-kit: kit moved from $recorded to $KIT_DIR; relinking"
bash "$KIT_DIR/install.sh" install
