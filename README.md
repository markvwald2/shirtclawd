# ClawdBot

ClawdBot is a lightweight content pipeline for ShirtClawd. It syncs shirt inventory, selects products to promote, generates AI-written social copy, writes post batches to disk, and can optionally publish to supported social platforms.

The repo is intentionally small and file-based. Most state lives in JSON and JSONL files under `data/` and `output/`.

For Mac laptop hosting, see `MAC_DEPLOYMENT.md`.
For Instagram setup, see `INSTAGRAM_SETUP.md`.
For the current go-to-market strategy, see `MARKETING_STRATEGY.md`.

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
- dry-run and live publishing to Instagram feed posts
- dry-run and live publishing to X with image upload
- a local dashboard for draft previews and usage metrics

## What It Does Not Do

ClawdBot does not currently:

- run its own scheduler
- publish directly to Facebook
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
  inventory_sync.py    Remote inventory fetch, metadata, snapshots
  instagram_publisher.py Instagram dry-run/live publishing for feed image posts
  planner.py           Daily planning and spend-aware platform selection
  post_generator.py    AI post shaping and platform formatting
  selector.py          Eligible shirt selection and promotion history helpers
  usage_logger.py      AI usage events, budget guards, run summaries
  writer.py            Output batch and index writing
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
  ai_usage.jsonl
  x_publish_log.jsonl
  snapshots/

output/
  posts_YYYY-MM-DD_<platform>.json
  post_index.json
  run_<timestamp>_<id>_summary.json

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

## Data Flow

ClawdBot follows a simple pipeline:

1. Optionally refresh inventory from the public dataset.
2. Load and normalize inventory records from `data/shirt_inventory.json`.
3. Merge local annotations from `data/shirt_annotations.json`.
4. Load promotion history from `data/promotion_history.json`.
5. Build a daily plan that chooses platforms and shirts within the estimated AI spend limit.
6. Select eligible shirts that are available, explicitly approved for promotion, and not recently promoted.
7. Generate copy with OpenAI.
8. Apply platform-specific formatting rules.
9. Write the post batch and update `output/post_index.json`.
10. Append promotion history entries.
11. Log AI usage events and write a per-run summary.
12. Optionally approve and publish individual X posts later.

## Configuration

### Theme Strategy

`config/theme_formats.json` defines audience assumptions and allowed post angles per theme.

### Platform Formatting

`config/content_formats.json` controls:

- hashtag count limits
- whether hashtags are appended to captions
- headline prefixes
- CTA suffixes

### Model Pricing

`config/model_pricing.json` is used only for estimated cost calculations in usage logs and summaries.

## State and Output Files

ClawdBot is file-based. Important files:

- `data/shirt_inventory.json`: current synced inventory
- `data/shirt_annotations.json`: local approval list, audience hints, and reference summaries
- `data/inventory_metadata.json`: source URL, fetch time, checksum, snapshot path
- `data/promotion_history.json`: generated-post history used for selection
- `data/x_approval_queue.json`: approved X posts
- `data/ai_usage.jsonl`: per-attempt AI usage and error events
- `data/x_publish_log.jsonl`: X dry-run and publish log
- `output/daily_plan_YYYY-MM-DD.json`: daily platform and shirt selection plan
- `output/posts_*.json`: generated post batches
- `output/post_index.json`: small index used by the UI
- `output/run_*_summary.json`: per-run aggregate metrics

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

### Instagram Publishing

Required for live publishing to Instagram:

- `INSTAGRAM_ACCESS_TOKEN`
- `INSTAGRAM_BUSINESS_ACCOUNT_ID`

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
