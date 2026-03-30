#!/bin/zsh

set -euo pipefail

REPO_ROOT="${0:A:h:h}"
cd "$REPO_ROOT"

if [[ -f ".env" ]]; then
  set -a
  source ".env"
  set +a
fi

if [[ ! -f "generate_posts.py" ]]; then
  echo "Run this script from the ShirtClawd repo."
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
DURATION_SECONDS="${DURATION_SECONDS:-3600}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-0}"
INSTAGRAM_ACCOUNT_ID="${INSTAGRAM_ACCOUNT_ID:-${INSTAGRAM_BUSINESS_ACCOUNT_ID:-}}"
STOP_ON_INSTAGRAM_LIMIT="${STOP_ON_INSTAGRAM_LIMIT:-0}"
START_TIME="$(date +%s)"
END_TIME="$((START_TIME + DURATION_SECONDS))"

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "Missing OPENAI_API_KEY."
  exit 1
fi

if [[ -z "${BLUESKY_HANDLE:-}" || -z "${BLUESKY_APP_PASSWORD:-}" ]]; then
  echo "Missing Bluesky credentials."
  exit 1
fi

if [[ -z "$INSTAGRAM_ACCOUNT_ID" || -z "${INSTAGRAM_ACCESS_TOKEN:-}" ]]; then
  echo "Missing Instagram credentials or account ID."
  exit 1
fi

round=1
while [[ "$(date +%s)" -lt "$END_TIME" ]]; do
  echo "== Round $round =="

  run_date="$(date -u +%F)"

  "$PYTHON_BIN" generate_posts.py --platform bluesky --writer-mode ai --count 1
  "$PYTHON_BIN" publish_to_bluesky.py --file "output/posts_${run_date}_bluesky.json" --index 0 --publish --force

  instagram_allowed=0
  if "$PYTHON_BIN" check_instagram_limit.py --account-id "$INSTAGRAM_ACCOUNT_ID" >/tmp/shirtclawd-instagram-limit.json 2>/tmp/shirtclawd-instagram-limit.err; then
    instagram_allowed=1
  else
    exit_code=$?
    if [[ "$exit_code" -eq 2 ]]; then
      echo "Instagram publish window exhausted; skipping Instagram generation and publishing this round."
      if [[ "$STOP_ON_INSTAGRAM_LIMIT" -eq 1 ]]; then
        echo "Stopping social run because Instagram hit the Meta publish limit."
        break
      fi
    else
      cat /tmp/shirtclawd-instagram-limit.err
      exit "$exit_code"
    fi
  fi

  if [[ "$instagram_allowed" -eq 1 ]]; then
    "$PYTHON_BIN" generate_posts.py --platform instagram --writer-mode ai --count 1
    set +e
    "$PYTHON_BIN" publish_to_instagram.py --file "output/posts_${run_date}_instagram.json" --index 0 --account-id "$INSTAGRAM_ACCOUNT_ID" --publish >/tmp/shirtclawd-instagram-publish.out 2>/tmp/shirtclawd-instagram-publish.err
    exit_code=$?
    set -e
    if [[ "$exit_code" -eq 0 ]]; then
      cat /tmp/shirtclawd-instagram-publish.out
    elif rg -q "Media Publish Limit Exceeded|2207042|User is performing too many actions" /tmp/shirtclawd-instagram-publish.out /tmp/shirtclawd-instagram-publish.err; then
      echo "Instagram publish window exhausted during publish; skipping Instagram this round."
      if [[ "$STOP_ON_INSTAGRAM_LIMIT" -eq 1 ]]; then
        echo "Stopping social run because Instagram hit the Meta publish limit."
        break
      fi
    else
      cat /tmp/shirtclawd-instagram-publish.out
      cat /tmp/shirtclawd-instagram-publish.err
      exit "$exit_code"
    fi
  fi

  round=$((round + 1))
  now="$(date +%s)"
  if [[ "$now" -ge "$END_TIME" ]]; then
    break
  fi

  remaining="$((END_TIME - now))"
  sleep_for="$INTERVAL_SECONDS"
  if [[ "$remaining" -lt "$sleep_for" ]]; then
    sleep_for="$remaining"
  fi
  if [[ "$sleep_for" -gt 0 ]]; then
    sleep "$sleep_for"
  fi
done

echo "Finished unleashed social run."
