#!/usr/bin/env bash
# Build a double-clickable "TV Photos.app" that runs `tv-photos run` in Terminal
# (so you see the live progress bar). The app is pinned to wherever this repo lives
# at build time. Re-run this script if you move the project.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$PROJECT_DIR/.venv/bin/python"
APP="$PROJECT_DIR/TV Photos.app"

if [[ ! -x "$PY" ]]; then
  echo "ERROR: venv python not found at $PY — create it first (uv venv)." >&2
  exit 1
fi

TMP="$(mktemp -t tvphotos).applescript"
cat > "$TMP" <<APPLESCRIPT
on run
	set cmd to "clear; cd '$PROJECT_DIR' && '$PY' -u -m tv_photos run; echo; echo '— Finished. You can close this window. —'"
	tell application "Terminal"
		activate
		do script cmd
	end tell
end run
APPLESCRIPT

rm -rf "$APP"
osacompile -o "$APP" "$TMP"
rm -f "$TMP"
echo "Built: $APP"
echo "Tip: drag it into /Applications or onto your Dock. First launch: right-click → Open"
echo "     (unsigned app), and approve 'control Terminal' when macOS asks."
