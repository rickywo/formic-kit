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

pause() {
  printf '\n%s' "Press Enter to close."
  read -r _ || true
}
