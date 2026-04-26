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
DURATION_SECONDS="${FOLLOW_UP_MODE_SECONDS:-3600}"
INTERVAL_SECONDS="${FOLLOW_UP_MODE_INTERVAL_SECONDS:-600}"
TARGET_CANDIDATES="${FOLLOW_UP_TARGET_CANDIDATES:-3}"
TARGET_SEARCH_LIMIT="${FOLLOW_UP_TARGET_SEARCH_LIMIT:-10}"
TARGET_MAX_AGE_DAYS="${FOLLOW_UP_TARGET_MAX_AGE_DAYS:-21}"
INBOX_LIMIT="${FOLLOW_UP_INBOX_LIMIT:-50}"
INBOX_LOOKBACK_HOURS="${FOLLOW_UP_INBOX_LOOKBACK_HOURS:-24}"
EXECUTE_APPROVED="${FOLLOW_UP_EXECUTE_APPROVED:-1}"
PUBLISH_APPROVED="${FOLLOW_UP_PUBLISH_APPROVED:-1}"
EXECUTE_LIMIT="${FOLLOW_UP_EXECUTE_LIMIT:-3}"
LEGACY_LOOP="${FOLLOW_UP_LEGACY_LOOP:-0}"

if [[ -z "${PYTHON_BIN:-}" ]]; then
  if [[ -x "$REPO_ROOT/.venv/bin/python3" ]]; then
    PYTHON_BIN="$REPO_ROOT/.venv/bin/python3"
  else
    PYTHON_BIN="python3"
  fi
fi

start_epoch="$(date +%s)"
end_epoch="$((start_epoch + DURATION_SECONDS))"
cycle=1

echo "Follow-up mode started at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Date: $PLAN_DATE"
echo "Duration seconds: $DURATION_SECONDS"
echo "Interval seconds: $INTERVAL_SECONDS"
echo "Approved execution: $EXECUTE_APPROVED"
echo "Publish approved Bluesky replies: $PUBLISH_APPROVED"
echo

if [[ "$LEGACY_LOOP" != "1" ]]; then
  session_args=(follow_up.py --daily-session \
    --date "$PLAN_DATE" \
    --uptime-minutes "$((DURATION_SECONDS / 60))" \
    --target-search-limit "$TARGET_SEARCH_LIMIT" \
    --target-candidates "$TARGET_CANDIDATES" \
    --target-max-age-days "$TARGET_MAX_AGE_DAYS" \
    --inbox-limit "$INBOX_LIMIT" \
    --inbox-lookback-hours "$INBOX_LOOKBACK_HOURS")

  if [[ "$EXECUTE_APPROVED" == "1" ]]; then
    session_args+=(--session-execute-approved --platform bluesky --limit "$EXECUTE_LIMIT")
  fi
  if [[ "$PUBLISH_APPROVED" == "1" ]]; then
    session_args+=(--publish)
  fi

  "$PYTHON_BIN" "${session_args[@]}"
  echo
  echo "Follow-up session completed at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  exit 0
fi

while (( $(date +%s) < end_epoch )); do
  now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "=== Cycle $cycle at $now ==="

  "$PYTHON_BIN" follow_up.py \
    --date "$PLAN_DATE" \
    --target-search-limit "$TARGET_SEARCH_LIMIT" \
    --target-candidates "$TARGET_CANDIDATES" || echo "Discovery refresh failed."

  if [[ "$EXECUTE_APPROVED" == "1" ]]; then
    execute_args=(follow_up.py --execute-approved --platform bluesky --limit "$EXECUTE_LIMIT")
    if [[ "$PUBLISH_APPROVED" == "1" ]]; then
      execute_args+=(--publish)
    fi
    "$PYTHON_BIN" "${execute_args[@]}" || echo "Approved action execution failed."
  fi

  "$PYTHON_BIN" follow_up.py --list-actions --date "$PLAN_DATE" --status approved || true
  "$PYTHON_BIN" follow_up.py --list-actions --date "$PLAN_DATE" --status drafted || true
  echo

  cycle="$((cycle + 1))"
  remaining="$((end_epoch - $(date +%s)))"
  if (( remaining <= 0 )); then
    break
  fi
  if (( remaining < INTERVAL_SECONDS )); then
    sleep "$remaining"
  else
    sleep "$INTERVAL_SECONDS"
  fi
done

echo "Follow-up mode completed at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
