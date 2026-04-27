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

previous_plan_date() {
  "$PYTHON_BIN" - "$1" <<'PY'
import sys
from datetime import date, timedelta

print((date.fromisoformat(sys.argv[1]) - timedelta(days=1)).isoformat())
PY
}

run_follow_up_session_for_date() {
  local session_date="$1"
  if [[ "${FOLLOW_UP_SESSION:-1}" != "1" ]]; then
    if [[ "${FOLLOW_UP_BRIEF:-1}" == "1" ]]; then
      "$PYTHON_BIN" follow_up.py --date "$session_date" --uptime-minutes "${FOLLOW_UP_UPTIME_MINUTES:-60}"
    fi
    return
  fi

  session_args=(follow_up.py --daily-session \
    --date "$session_date" \
    --uptime-minutes "${FOLLOW_UP_UPTIME_MINUTES:-60}" \
    --target-search-limit "${FOLLOW_UP_TARGET_SEARCH_LIMIT:-10}" \
    --target-candidates "${FOLLOW_UP_TARGET_CANDIDATES:-3}" \
    --target-max-age-days "${FOLLOW_UP_TARGET_MAX_AGE_DAYS:-21}" \
    --inbox-limit "${FOLLOW_UP_INBOX_LIMIT:-50}" \
    --inbox-lookback-hours "${FOLLOW_UP_INBOX_LOOKBACK_HOURS:-24}")

  if [[ "${FOLLOW_UP_EXECUTE_APPROVED:-1}" == "1" ]]; then
    session_args+=(--session-execute-approved --platform bluesky --limit "${FOLLOW_UP_EXECUTE_LIMIT:-3}")
  fi
  if [[ "$AUTO_PUBLISH" == "1" && "${FOLLOW_UP_PUBLISH_APPROVED:-1}" == "1" ]]; then
    session_args+=(--publish)
  fi

  "$PYTHON_BIN" "${session_args[@]}"
}

if [[ "${FOLLOW_UP_PREFLIGHT:-1}" == "1" ]]; then
  PREFLIGHT_DATE="${FOLLOW_UP_PREFLIGHT_DATE:-$(previous_plan_date "$PLAN_DATE")}"
  if [[ -f "output/daily_plan_${PREFLIGHT_DATE}.json" ]]; then
    echo "Running preflight follow-up session for $PREFLIGHT_DATE"
    run_follow_up_session_for_date "$PREFLIGHT_DATE"
  else
    echo "No preflight follow-up plan found for $PREFLIGHT_DATE; skipping."
  fi
fi

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
  run_follow_up_session_for_date "$PLAN_DATE"
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

run_follow_up_session_for_date "$PLAN_DATE"
