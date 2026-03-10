# ClawdBot

ClawdBot is an automated content generator for the ShirtClawd project. It reads structured shirt inventory data, selects items that should be promoted, and generates ready-to-post social media content.

The system is designed to be **lightweight, deterministic where possible, and inexpensive to run**, minimizing AI token usage while still producing engaging posts.

---

# Overview

ClawdBot's job is to:

1. Read shirt inventory data from a **source-of-truth dataset**.
2. Select shirts that should be promoted.
3. Generate social media posts.
4. Output structured post content ready for publishing.

The bot is intended to run on a schedule (for example, a few hours per day) and produce a small number of posts each run.

---

# Source of Truth

ClawdBot does **not** maintain its own inventory.

Instead it pulls from the public dataset:

`data/shirt_inventory.json`

Example record:

```json
{
  "shirt_id": "5d89cc30f937647d81ffc564",
  "title": "Biblical Sense",
  "tags": ["bible", "Jesus", "Bible", "Christianity", "religion"],
  "url": "https://thirdstringshirts.com/...",
  "image_url": "...",
  "status": "available"
}
```

This dataset is treated as the **canonical data source**.

ClawdBot only reads from it.

---

# Core Responsibilities

## 1. Load Inventory

ClawdBot reads the inventory dataset and builds an in-memory representation of available shirts.

Basic validation is performed:

* required fields present
* duplicates avoided
* status filtering (ex: available shirts only)

---

## 2. Select Shirts to Promote

Selection logic may include:

* shirts not recently promoted
* random sampling
* category rotation
* seasonal relevance
* tag-based selection

The goal is to keep the feed varied.

---

## 3. Generate Post Content

For each selected shirt, ClawdBot generates:

* headline
* caption text
* hashtags
* optional alt text

Example output:

```
Title: Biblical Sense

Caption:
Faith meets fashion. Biblical Sense is perfect for anyone who enjoys a little divine humor.

Hashtags:
#funnyshirts #biblehumor #thirdstringshirts
```

Posts are generated in a consistent structure so they can be easily published.

---

## 4. Output Posts

Posts are written to structured output files.

Example:

```
output/posts_2026-03-04.json
```

Example structure:

```json
{
  "shirt_id": "5d89cc30f937647d81ffc564",
  "title": "Biblical Sense",
  "caption": "...",
  "hashtags": ["#funnyshirts", "#biblehumor"],
  "image_url": "...",
  "url": "..."
}
```

These outputs can be consumed by publishing tools or automation workflows.

---

# Design Goals

## Low Token Usage

AI generation is used sparingly.

Strategies include:

* deterministic formatting
* template-based posts
* batching prompts
* limiting max tokens

---

## Deterministic Data Pipeline

Inventory data is **never modified** by the bot.

All state changes (such as tracking previously promoted shirts) are stored separately.

---

## Simple Deployment

ClawdBot is designed to run:

* locally
* via cron
* in a lightweight CI job
* or a scheduled container

---

# Example Workflow

```
1. Fetch inventory dataset
2. Filter eligible shirts
3. Select shirts to promote
4. Generate captions
5. Write post output files
```

---

# Running ClawdBot

Example:

```bash
python generate_posts.py
```

Output will appear in:

```
/output
```

---

# Future Enhancements

Possible improvements:

* track previously posted shirts
* schedule posts automatically
* platform-specific formatting (Twitter, Instagram, etc.)
* analytics feedback loop
* meme-style caption generation
* seasonal / trending tag detection

---

# Philosophy

ClawdBot exists to **scale humor and promotion without manual effort**.

By combining structured shirt data with lightweight AI generation, the system produces consistent content while remaining cheap and easy to maintain.