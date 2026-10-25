#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Use the existing checkout; cloud tasks are already isolated.
python3 -c 'import sys; assert sys.version_info >= (3,12), "Python 3.12+ required"'
node -e 'if (+process.versions.node.split(".")[0] < 22) throw Error("Node 22+ required")'
LIFEPLAN_VENV="${LIFEPLAN_VENV:-/workspace/.lifeplan-venv}"
python3 -m venv "$LIFEPLAN_VENV"
"$LIFEPLAN_VENV/bin/python" -m pip install --requirement requirements-dev.txt
if command -v chromium >/dev/null 2>&1; then
  echo "Browser tests: export CHROMIUM_PATH=$(command -v chromium)"
else
  PLAYWRIGHT_BROWSERS_PATH=/workspace/.lifeplan-browsers "$LIFEPLAN_VENV/bin/python" -m playwright install chromium
fi
