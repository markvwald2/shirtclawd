# Codex Workflows

These are the highest-frequency non-development tasks to do from Codex in this repo.

## 1. Generate New Posts

Best Codex prompt:

```text
Generate 2 new Instagram posts for promotable shirts that fit the Coloradans Against theme. Show me the drafts and the output file path.
```

Useful repo command:

```bash
python shirtclawd.py ask "Write 2 posts for Instagram for the Coloradans Against shirts"
```

Notes:

- Instagram generation still works.
- Instagram can be published directly through the repo again when credentials are configured.
- Bluesky can still be published directly if needed.

## 2. Add a New Shirt to Inventory

Best Codex prompt:

```text
Add this shirt to ShirtClawd inventory:
shirt_id: abc123
title: Biblical Sense
product_url: https://example.com/biblical-sense
image_url: https://example.com/biblical-sense.jpg
theme: religion
sub_theme: Bible jokes
tags: religion, funny, wordplay
```

Useful repo command:

```bash
python manage_catalog.py add-shirt \
  --shirt-id abc123 \
  --title "Biblical Sense" \
  --product-url "https://example.com/biblical-sense" \
  --image-url "https://example.com/biblical-sense.jpg" \
  --theme religion \
  --sub-theme "Bible jokes" \
  --tag "religion, funny, wordplay"
```

## 3. Mark a Shirt as Promotable and Add Metadata

Best Codex prompt:

```text
Mark shirt abc123 as promotable and add the metadata needed for generation:
reference_summary: A dry Bible joke for church-camp adults.
target_audience: church humor fans, wordplay fans
tone: dry_wordplay
tone_notes: Keep it dry and lightly smug.
notes: Strong niche fit.
```

Useful repo command:

```bash
python manage_catalog.py promote-shirt \
  --shirt-id abc123 \
  --reference-summary "A dry Bible joke for church-camp adults." \
  --audience "church humor fans, wordplay fans" \
  --tone dry_wordplay \
  --tone-notes "Keep it dry and lightly smug." \
  --notes "Strong niche fit."
```

## 4. Build Today's Follow-Up Brief

Best Codex prompt:

```text
Run today's ShirtClawd follow-up session.
```

Useful repo command:

```bash
python follow_up.py --daily-session --date 2026-04-26
```

Notes:

- The daily workflow first runs a previous-day follow-up preflight when a prior daily plan exists, publishes fresh posts, then runs today's follow-up session automatically before exiting.
- The follow-up session writes `output/follow_up_YYYY-MM-DD.md` and `output/follow_up_session_YYYY-MM-DD.md`, scans Bluesky replies/mentions/quotes since the last saved check, refreshes candidate targets, updates the queue, and exits.
- The same run updates `data/follow_up_action_queue.json` with action IDs and statuses, plus `data/follow_up_session_state.json` with the next inbox checkpoint.
- Public replies, comments, DMs, follows, and offers still require human approval.
- Target discovery runs by default for Bluesky, Threads, Instagram, and curated Facebook review targets. Use `--skip-target-discovery` for offline/manual-only runs.
- Use `--automation-only` or `FOLLOW_UP_AUTOMATION_ONLY=1` when you want the queue to contain only API-executable follow-ups; manual-only targets are suppressed for that run date.

Approval flow:

```bash
python follow_up.py --list-actions --date 2026-04-26
python follow_up.py --approve FU-2026-04-26-01-R1 --target-url "https://example.com/target-post" --copy "Final text"
python follow_up.py --approve FU-2026-04-26-01-R1 --copy "Final text"
python follow_up.py --daily-session --date 2026-04-26 --session-execute-approved
python follow_up.py --daily-session --date 2026-04-26 --session-execute-approved --publish --limit 3
python follow_up.py --daily-session --date 2026-04-26 --automation-only --session-execute-approved --publish
python follow_up.py --execute-approved --platform bluesky
python follow_up.py --execute-approved --publish --limit 3
python follow_up.py --mark-sent FU-2026-04-26-01-R1 --target-url "https://example.com/target-post"
python follow_up.py --skip FU-2026-04-26-O1 --note "Not the right audience"
```

Execution notes:

- `--execute-approved` is a dry run unless `--publish` is passed.
- In daily session mode, `--session-execute-approved` runs approved supported actions during the catch-up pass; `--publish` decides dry run vs live publish.
- The first supported execution path is Bluesky replies to `bsky.app` post URLs or `at://` post URIs.
- Instagram, Facebook, Threads, and outreach DMs stay in the approval queue for manual sending until their safe executors are added.

## Recommended Codex Pattern

When working in chat, the fastest pattern is:

1. Add the shirt to inventory.
2. Mark it promotable with metadata.
3. Ask Codex to generate posts for that shirt or theme.

That keeps the repo state clean and makes future generation work without extra manual edits.
