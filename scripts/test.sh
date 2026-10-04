#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON=python3
[ -x .venv/bin/python ] && PYTHON=.venv/bin/python
if ! "$PYTHON" -m pytest --version > /dev/null 2>&1; then
  echo "✗ pytest is not installed for $PYTHON; run: bash scripts/setup-python.sh" >&2
  exit 1
fi

bash scripts/check-lifecycle.sh
bash scripts/test-lifecycle.sh
"$PYTHON" -m unittest discover -s scripts/tests -q
"$PYTHON" -m pytest -q
