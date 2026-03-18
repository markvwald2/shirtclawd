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

PLAN_DATE="${PLAN_DATE:-$(date +%F)}"
PYTHON_BIN="${PYTHON_BIN:-$REPO_ROOT/.venv/bin/python3}"

"$PYTHON_BIN" plan_day.py --date "$PLAN_DATE" --max-estimated-cost 1.0
"$PYTHON_BIN" generate_posts.py --plan "output/daily_plan_${PLAN_DATE}.json"
