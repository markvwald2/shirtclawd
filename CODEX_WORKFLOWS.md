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

## Recommended Codex Pattern

When working in chat, the fastest pattern is:

1. Add the shirt to inventory.
2. Mark it promotable with metadata.
3. Ask Codex to generate posts for that shirt or theme.

That keeps the repo state clean and makes future generation work without extra manual edits.
