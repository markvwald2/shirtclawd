#!/bin/zsh

set -euo pipefail

REPO_ROOT="${0:A:h:h}"
cd "$REPO_ROOT"

if [[ -f ".env" ]]; then
  set -a
  source ".env"
  set +a
fi

if [[ ! -d ".venv" ]]; then
  echo "Missing .venv in $REPO_ROOT"
  exit 1
fi

mkdir -p logs output

PYTHON_BIN="${PYTHON_BIN:-$REPO_ROOT/.venv/bin/python3}"
"$PYTHON_BIN" publish_approved_x_queue.py --publish
