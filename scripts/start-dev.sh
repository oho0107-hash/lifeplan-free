#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Serve a whitelist, never the checkout containing review files or Git metadata.
LIFEPLAN_PYTHON="${LIFEPLAN_PYTHON:-/workspace/.lifeplan-venv/bin/python}"
LIFEPLAN_PUBLIC="$(mktemp -d /tmp/lifeplan-public.XXXXXX)"
trap 'rm -rf "$LIFEPLAN_PUBLIC"' EXIT
mkdir -p "$LIFEPLAN_PUBLIC/costs"
cp index.html education-reserve.html "$LIFEPLAN_PUBLIC/"
cp costs/official_sources.json "$LIFEPLAN_PUBLIC/costs/"
"$LIFEPLAN_PYTHON" -m http.server "${PORT:-8000}" --bind 127.0.0.1 --directory "$LIFEPLAN_PUBLIC"
