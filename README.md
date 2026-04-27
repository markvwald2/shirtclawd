# ClawdBot

ClawdBot is a lightweight content pipeline for ShirtClawd. It syncs shirt inventory, selects products to promote, generates AI-written social copy, writes post batches to disk, and can optionally publish to selected social platforms.

The repo is intentionally small and file-based. Most state lives in JSON and JSONL files under `data/` and `output/`.

For Mac laptop hosting, see `MAC_DEPLOYMENT.md`.
For the current go-to-market strategy, see `MARKETING_STRATEGY.md`.
For common Codex operations, see `CODEX_WORKFLOWS.md`.

## What It Does

ClawdBot currently supports:

- inventory sync from the public ShirtClawd source dataset
- inventory normalization and validation
- local annotation merge for approval-only promotion eligibility and reference context
- promotion history tracking
- daily planning with spend-aware platform selection
- AI-assisted post generation
- platform-specific formatting for Instagram, Facebook, X, Bluesky, Reels, and TikTok
- AI usage, latency, token, and cost logging
- budget guards that stop generation before overrun
- X approval queue management
- Bluesky approval-gated publishing with image upload
- dry-run and live publishing to Facebook Page feed posts
- dry-run and live publishing to Threads posts with optional image attachment
- dry-run and live publishing to Instagram feed posts
- dry-run and live publishing to X with image upload
- a local dashboard for draft previews and usage metrics

## What It Does Not Do

ClawdBot does not currently:

- run its own scheduler
- maintain a feedback loop from post performance
- discover trends or seasonal topics from external sources
- edit or enrich product images
- act as a full analytics or optimization system

## Repo Layout

```text
bot/
  ai_writer.py         OpenAI Responses API client and response validation
  approval_queue.py    File-based approval storage for X publishing
  data_loader.py       Inventory normalization, validation, dedupe
  facebook_publisher.py Facebook Page dry-run/live publishing for feed/link posts
  instagram_publisher.py Instagram dry-run/live publishing for feed image posts
  inventory_sync.py    Remote inventory fetch, metadata, snapshots
  planner.py           Daily planning and spend-aware platform selection
  post_generator.py    AI post shaping and platform formatting
  selector.py          Eligible shirt selection and promotion history helpers
  usage_logger.py      AI usage events, budget guards, run summaries
  writer.py            Output batch and index writing
  threads_publisher.py Threads dry-run/live publishing with optional image attachment
  x_publisher.py       X dry-run/live publishing and media upload

config/
  content_formats.json Platform formatting rules
  model_pricing.json   Estimated AI pricing data
  theme_formats.json   Theme-specific audience and angle settings

data/
  shirt_inventory.json Current local inventory snapshot
  shirt_annotations.json Local editorial metadata keyed by shirt_id
  inventory_metadata.json
  promotion_history.json
  x_approval_queue.json
  follow_up_action_queue.json
  follow_up_execution_log.jsonl
  ai_usage.jsonl
  x_publish_log.jsonl
  snapshots/

output/
  posts_YYYY-MM-DD_<platform>.json
  post_index.json
  run_<timestamp>_<id>_summary.json
  follow_up_YYYY-MM-DD.md

ui/
  index.html
  app.js
  styles.css

tests/
  Unit tests for sync, selection, generation, approvals, publishing, and budget guards
```

## Main Entry Points

### Build Daily Plan

```bash
python plan_day.py
```

Useful flags:

```bash
python plan_day.py \
  --platform x \
  --platform instagram \
  --platform facebook \
  --platform bluesky \
  --max-estimated-cost 1.0
```

Campaign mode can pin the day to a specific audience lane instead of broad catalog rotation:

```bash
python plan_day.py \
  --campaign coloradans_against \
  --platform bluesky \
  --platform instagram \
  --platform facebook \
  --platform threads \
  --no-approval-required
```

The scheduled daily workflow defaults to this campaign. It first runs a preflight follow-up session for the previous daily plan when one exists, then auto-publishes today's generated posts, then runs today's follow-up session before exiting:

```bash
scripts/run_daily_workflow.sh
```

Set `AUTO_PUBLISH=0` to generate without publishing, `FOLLOW_UP_PREFLIGHT=0` to skip the previous-day catch-up pass, `FOLLOW_UP_SESSION=0` to skip follow-up sessions, or override `PLATFORMS` with a space-separated list.

### Generate Posts

```bash
python generate_posts.py
```

Useful flags:

```bash
python generate_posts.py \
  --plan output/daily_plan_2026-03-14.json
```

Or continue to run a single platform directly:

```bash
python generate_posts.py \
  --platform instagram \
  --writer-mode ai \
  --count 3 \
  --refresh-inventory
```

Supported platforms:

- `instagram`
- `facebook`
- `x`
- `bluesky`
- `threads`
- `reels`
- `tiktok`

Supported writer modes:

- `ai`: OpenAI only, fail hard if AI generation fails or if budget guards trigger

### Natural-Language Generation

You can also drive generation with a plain-English command:

```bash
python shirtclawd.py ask "Write 2 posts for Instagram for the Coloradans Against shirts"
```

Current support is intentionally narrow:

- generation requests only
- one platform per command
- optional product/theme filter after the platform clause

The command prints the parsed intent, the matched shirts, and the generated output path.

### Sync Inventory

```bash
python sync_inventory.py
```

This fetches the canonical inventory JSON, writes `data/shirt_inventory.json`, records fetch metadata, and stores a timestamped snapshot in `data/snapshots/`.

### Manage Catalog

```bash
python manage_catalog.py --help
```

Use this to add new shirts to inventory and to mark shirts promotable with local metadata for generation.

### Approve a Post for X

```bash
python approve_post.py --file output/posts_2026-03-10_x.json --index 0
```

Approvals are stored in `data/x_approval_queue.json`.

### Publish to X

Dry run:

```bash
python publish_to_x.py --file output/posts_2026-03-10_x.json --index 0
```

Live publish:

```bash
python publish_to_x.py --file output/posts_2026-03-10_x.json --index 0 --publish
```

By default, live publishing requires a prior approval entry unless `--force` is used.

### Publish to Facebook

Dry run:

```bash
python publish_to_facebook.py --file output/posts_2026-03-14_facebook.json --index 0
```

Live publish:

```bash
python publish_to_facebook.py --file output/posts_2026-03-14_facebook.json --index 0 --publish
```

Batch publish approved X posts:

```bash
python publish_approved_x_queue.py --publish
```

### Publish to Bluesky

Dry run:

```bash
python publish_to_bluesky.py --file output/posts_2026-03-10_bluesky.json --index 0
```

Live publish:

```bash
python publish_to_bluesky.py --file output/posts_2026-03-10_bluesky.json --index 0 --publish
```

By default, live publishing requires a prior approval entry unless `--force` is used.

### Publish to Threads

Dry run:

```bash
python publish_to_threads.py --file output/posts_2026-03-10_threads.json --index 0
```

Live publish:

```bash
python publish_to_threads.py --file output/posts_2026-03-10_threads.json --index 0 --publish
```

Current support publishes image posts when `image_url` is present and falls back to text-only otherwise.

### Publish to Instagram

Dry run:

```bash
python publish_to_instagram.py --file output/posts_2026-03-22_instagram.json --index 0
```

Live publish:

```bash
python publish_to_instagram.py --file output/posts_2026-03-22_instagram.json --index 0 --publish
```

The CLI auto-loads `.env` if it exists. Current support is limited to single-image feed posts.

### Run a Daily Follow-Up Session

For the one-hour supervised pilot, prefer the daily catch-up session. It checks the saved queue, refreshes candidate targets, scans Bluesky replies/mentions/quotes since the last session, writes a review report, executes already-approved Bluesky replies when requested, saves the new last-checked timestamp, and exits.

```bash
python follow_up.py --daily-session --date 2026-04-26
```

The session writes:

- `output/follow_up_YYYY-MM-DD.md`: the full draft/review brief.
- `output/follow_up_session_YYYY-MM-DD.md`: the catch-up summary and current to-dos.
- `data/follow_up_session_state.json`: the last checked timestamp for tomorrow's inbox scan.

Execute approved Bluesky replies during the same catch-up pass:

```bash
python follow_up.py --daily-session --date 2026-04-26 --session-execute-approved --publish --limit 3
```

`scripts/run_follow_up_mode.sh` now runs this one-shot session by default. Set `FOLLOW_UP_LEGACY_LOOP=1` only if you want the old 10-minute discovery/execution loop.

### Build a Follow-Up Brief

After a campaign publishes, generate a one-hour distribution checklist:

```bash
python follow_up.py --date 2026-04-26
```

The brief is written to `output/follow_up_YYYY-MM-DD.md`. It reads the daily plan, generated post files, and publish logs, then produces discovery searches, candidate target posts/accounts, reply/comment drafts, creator outreach prompts, and a tracking table. Public replies, comments, DMs, follows, and offers are intentionally approval-gated. This is still available as a lower-level command, but the daily session above is the recommended morning workflow.

`scripts/run_daily_workflow.sh` now runs a previous-day follow-up preflight before publishing and the full daily follow-up session after publishing unless disabled. Use `FOLLOW_UP_PREFLIGHT=0` to skip the previous-day pass, and `FOLLOW_UP_UPTIME_MINUTES`, `FOLLOW_UP_INBOX_LIMIT`, `FOLLOW_UP_EXECUTE_APPROVED`, and `FOLLOW_UP_PUBLISH_APPROVED` to tune follow-up behavior. If `FOLLOW_UP_SESSION=0`, the older brief-only behavior still runs when `FOLLOW_UP_BRIEF=1`.

Discovery coverage:

- Bluesky: public post search with concrete `bsky.app` post targets.
- Threads: official keyword search when `THREADS_ACCESS_TOKEN` has the required search permission.
- Instagram: hashtag discovery through the Instagram Graph API using `INSTAGRAM_ACCESS_TOKEN` and `INSTAGRAM_BUSINESS_ACCOUNT_ID`.
- Facebook: curated page/account review targets from `config/facebook_discovery_targets.json`, because broad public post search is not available through the normal Graph API.

The same command also updates `data/follow_up_action_queue.json` with approval IDs such as `FU-2026-04-26-01-R1`.

List today's actions:

```bash
python follow_up.py --list-actions --date 2026-04-26
```

Approve an action after reviewing the suggested target post or choosing your own:

```bash
python follow_up.py \
  --approve FU-2026-04-26-01-R1 \
  --target-url "https://example.com/target-post" \
  --copy "Final approved reply text"
```

If the bot already attached the right candidate target, `--target-url` is optional and approval can just set the final copy:

```bash
python follow_up.py --approve FU-2026-04-26-01-R1 --copy "Final approved reply text"
```

After you manually post or send it, mark it sent:

```bash
python follow_up.py --mark-sent FU-2026-04-26-01-R1 --target-url "https://example.com/target-post"
```

Skip weak fits:

```bash
python follow_up.py --skip FU-2026-04-26-O1 --note "Not the right audience"
```

Run approved actions as a dry run:

```bash
python follow_up.py --execute-approved --platform bluesky
```

Execute approved Bluesky replies:

```bash
python follow_up.py --execute-approved --platform bluesky --publish --limit 3
```

Execution is intentionally narrow in the supervised pilot. Bluesky reply/comment actions can execute when the approved action has a `target_url` that is either a `bsky.app` post URL or an `at://` post URI. Instagram, Facebook, Threads, and outreach DMs remain approval-tracked but manually sent until their platform-specific execution paths are added.

## Data Flow

ClawdBot follows a simple pipeline:

1. Run a previous-day follow-up preflight when a prior daily plan exists.
2. Optionally refresh inventory from the public dataset.
3. Load and normalize inventory records from `data/shirt_inventory.json`.
4. Merge local annotations from `data/shirt_annotations.json`.
5. Load promotion history from `data/promotion_history.json`.
6. Build a daily plan that chooses platforms and shirts within the estimated AI spend limit.
7. Optionally apply campaign metadata such as `coloradans_against`, content goals, CTA goals, and audience lane.
8. Select eligible shirts that are available, explicitly approved for promotion, and not recently promoted.
9. Generate copy with OpenAI.
10. Apply platform-specific formatting rules.
11. Write the post batch and update `output/post_index.json`.
12. Append promotion history entries.
13. Log AI usage events and write a per-run summary.
14. Publish configured platforms when the workflow is in live mode.
15. Run today's follow-up session to scan inbox items, refresh to-dos, execute approved supported actions, and save the next inbox checkpoint.

## Configuration

### Theme Strategy

`config/theme_formats.json` defines audience assumptions and allowed post angles per theme.

### Platform Formatting

`config/content_formats.json` controls:

- hashtag count limits
- whether hashtags are appended to captions
- headline prefixes
- CTA suffixes

### Campaign Modes

`bot/campaigns.py` defines campaign lanes that can override broad shirt rotation.

Current campaign:

- `coloradans_against`: selects the `Coloradans Against` shirts, adds campaign/series/audience metadata, includes the current 25% off Coloradans Against / 20% off all other shirts offer through April 29, 2026, and rotates content goals across conversation, shareable local argument, series spotlight, and direct offer posts.

### Model Pricing

`config/model_pricing.json` is used only for estimated cost calculations in usage logs and summaries.

## State and Output Files

ClawdBot is file-based. Important files:

- `data/shirt_inventory.json`: current synced inventory
- `data/shirt_annotations.json`: local approval list, audience hints, and reference summaries
- `data/inventory_metadata.json`: source URL, fetch time, checksum, snapshot path
- `data/promotion_history.json`: generated-post history used for selection
- `data/x_approval_queue.json`: approved X posts
- `data/follow_up_action_queue.json`: drafted, approved, sent, and skipped follow-up actions
- `data/follow_up_execution_log.jsonl`: dry-run, sent, unsupported, and error results for follow-up execution
- `data/ai_usage.jsonl`: per-attempt AI usage and error events
- `data/x_publish_log.jsonl`: X dry-run and publish log
- `data/threads_publish_log.jsonl`: Threads dry-run and publish log
- `output/daily_plan_YYYY-MM-DD.json`: daily platform and shirt selection plan
- `output/posts_*.json`: generated post batches
- `output/post_index.json`: small index used by the UI
- `output/run_*_summary.json`: per-run aggregate metrics
- `output/follow_up_YYYY-MM-DD.md`: post-publish distribution brief

## Environment Variables

### OpenAI

Required for generation:

- `OPENAI_API_KEY`
- `OPENAI_MODEL` optional override

### X Publishing

Required for live publishing to X:

- `X_API_KEY`
- `X_API_KEY_SECRET`
- `X_ACCESS_TOKEN`
- `X_ACCESS_TOKEN_SECRET`

### Bluesky Publishing

Required for live publishing to Bluesky:

- `BLUESKY_HANDLE`
- `BLUESKY_APP_PASSWORD`

### Threads Publishing And Discovery

Required for live publishing and keyword discovery on Threads:

- `THREADS_ACCESS_TOKEN`
- `THREADS_USER_ID`
- `THREADS_USERNAME` optional self-exclusion hint for discovery

### Instagram Publishing And Discovery

Required for live publishing and hashtag discovery on Instagram:

- `INSTAGRAM_ACCESS_TOKEN`
- `INSTAGRAM_BUSINESS_ACCOUNT_ID`

### Facebook Publishing And Discovery

Required for live publishing to Facebook:

- `FACEBOOK_PAGE_ACCESS_TOKEN`
- `FACEBOOK_PAGE_ID`

Facebook discovery uses curated review targets in `config/facebook_discovery_targets.json`; it does not require broad public post search access.

## Local Dashboard

The `ui/` directory contains a small static dashboard that reads:

- `output/post_index.json`
- generated post batch files in `output/`
- `data/ai_usage.jsonl`
- `data/x_approval_queue.json`

It is for inspection only. It does not trigger generation, approval, or publishing actions.

## Testing

Run the unit suite with:

```bash
python3 -m unittest discover -s tests
```

## Design Notes

ClawdBot is optimized for:

- low operational complexity
- low AI spend
- fail-fast behavior when AI generation or budget checks fail
- plain JSON artifacts that are easy to inspect and automate around

It is not designed as a long-running service. It is a batch-oriented toolchain that can be scheduled externally.

## Marketing Direction

The current canonical marketing strategy lives in `MARKETING_STRATEGY.md`.

The working thesis is:

- ShirtClawd should grow by behaving like a niche publisher, not a generic merch scheduler
- the first audience beachhead is the `Coloradans Against` series
- content should entertain first, sell second
- owned audience capture matters as much as social posting
