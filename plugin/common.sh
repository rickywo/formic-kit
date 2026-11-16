# Shared helpers for the herdr plugin scripts. Sourced, not run.

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERDR="${HERDR_BIN_PATH:-herdr}"

# The folder the user is working in: the focused pane's directory, else the workspace's.
context_dir() {
  python3 - <<'PY'
import json, os
try:
    c = json.loads(os.environ.get("HERDR_PLUGIN_CONTEXT_JSON") or "{}")
except ValueError:
    c = {}
print(c.get("focused_pane_cwd") or c.get("workspace_cwd") or "")
PY
}

# The project root for a folder: the nearest parent with .formic, else the git root, else the folder.
project_root() {
  local dir="$1" d
  [ -n "$dir" ] && [ -d "$dir" ] || { printf '%s\n' ""; return 0; }
  d="$(cd "$dir" && pwd)"
  while [ "$d" != "/" ]; do
    [ -d "$d/.formic" ] && { printf '%s\n' "$d"; return 0; }
    d="$(dirname "$d")"
  done
  git -C "$dir" rev-parse --show-toplevel 2>/dev/null || (cd "$dir" && pwd)
}

# After a plugin update the kit lives in a new folder. Point the skill links and agent
# profiles at it before doing anything else. Quiet when nothing moved or setup has not
# been run; never stops the caller.
relink_if_moved() {
  local state="${FORMIC_KIT_STATE_DIR:-$HOME/.config/formic-kit}/config" recorded
  [ -f "$state" ] || return 0
  recorded="$(awk -F= '$1 == "kit_dir" { print substr($0, 9) }' "$state")"
  [ "$recorded" = "$KIT_DIR" ] && return 0
  echo "formic-kit: kit moved from $recorded to $KIT_DIR; relinking" >&2
  bash "$KIT_DIR/install.sh" install >&2 || echo "formic-kit: relink failed; run the setup action" >&2
  return 0
}

# The value of one key in the settings file that install.sh saves. Prints nothing when the
# file or the key is missing. Always succeeds.
saved_setting() {
  local file="${FORMIC_KIT_STATE_DIR:-$HOME/.config/formic-kit}/config"
  [ -f "$file" ] || return 0
  awk -F= -v k="$1" '$1 == k { print substr($0, length(k) + 2); exit }' "$file"
  return 0
}

# The runtime that runs the coordinator and the workers: opencode (the default) or claude.
saved_runtime() {
  local r
  r="$(saved_setting runtime)"
  printf '%s\n' "${r:-opencode}"
}

pause() {
  printf '\n%s' "Press Enter to close."
  read -r _ || true
}
