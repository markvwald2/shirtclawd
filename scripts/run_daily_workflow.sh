#!/bin/zsh

set -euo pipefail

REPO_ROOT="${0:A:h:h}"
cd "$REPO_ROOT"

if [[ -f ".env" ]]; then
  set -a
  source ".env"
  set +a
fi

mkdir -p logs output

PLAN_DATE="${PLAN_DATE:-$(date +%F)}"
if [[ -z "${PYTHON_BIN:-}" ]]; then
  if [[ -x "$REPO_ROOT/.venv/bin/python3" ]]; then
    PYTHON_BIN="$REPO_ROOT/.venv/bin/python3"
  else
    PYTHON_BIN="python3"
  fi
fi
CAMPAIGN="${CAMPAIGN:-coloradans_against}"
AUTO_PUBLISH="${AUTO_PUBLISH:-1}"
PLATFORMS=("${(@s: :)${PLATFORMS:-bluesky instagram facebook threads}}")

plan_args=(plan_day.py --date "$PLAN_DATE" --max-estimated-cost 1.0 --campaign "$CAMPAIGN" --no-approval-required)
for platform in "${PLATFORMS[@]}"; do
  plan_args+=(--platform "$platform")
done

"$PYTHON_BIN" "${plan_args[@]}"
"$PYTHON_BIN" generate_posts.py --plan "output/daily_plan_${PLAN_DATE}.json"

latest_posts_file() {
  local platform="$1"
  "$PYTHON_BIN" - "$platform" <<'PY'
import json
import sys
from pathlib import Path

platform = sys.argv[1]
index_path = Path("output/post_index.json")
if not index_path.exists():
    raise SystemExit(f"Missing {index_path}")

payload = json.loads(index_path.read_text())
for entry in payload.get("files", []):
    if entry.get("platform") == platform:
        print(entry["path"])
        break
else:
    raise SystemExit(f"No post index entry found for platform={platform}")
PY
}

if [[ "$AUTO_PUBLISH" != "1" ]]; then
  echo "AUTO_PUBLISH=$AUTO_PUBLISH; skipping publish step."
  exit 0
fi

for platform in "${PLATFORMS[@]}"; do
  posts_file="$(latest_posts_file "$platform")"
  case "$platform" in
    bluesky)
      "$PYTHON_BIN" publish_to_bluesky.py --file "$posts_file" --index 0 --publish --force
      ;;
    instagram)
      "$PYTHON_BIN" publish_to_instagram.py --file "$posts_file" --index 0 --publish
      ;;
    facebook)
      "$PYTHON_BIN" publish_to_facebook.py --file "$posts_file" --index 0 --publish
      ;;
    threads)
      "$PYTHON_BIN" publish_to_threads.py --file "$posts_file" --index 0 --publish
      ;;
    *)
      echo "No auto-publish command configured for platform=$platform"
      ;;
  esac
done
