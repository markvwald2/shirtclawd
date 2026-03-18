# ClawdBot Roadmap

This document describes the intended implementation sequence for ClawdBot as it evolves from a single-platform content generator into a multi-platform, budget-aware marketing system.

It is meant to answer two questions:

- what are we trying to build?
- what should we build next, in what order?

## Target End State

The desired long-term flow is:

1. Generate and publish content across worthwhile platforms such as X, Instagram, Facebook, and Bluesky.
2. Respect explicit business judgment about which shirts should and should not be promoted.
3. Match shirts, copy, and platforms to specific audiences or demographics.
4. Operate within daily posting and AI budget limits while maximizing marketing value.

## Planning Principles

The order matters.

ClawdBot should not attempt trend detection or audience targeting until the following are stable:

- platform publishing architecture
- promotion eligibility controls
- daily planning and budget enforcement

Without those layers, the bot will optimize against the wrong inventory and inconsistent delivery channels.

## Current State

Today the repo already supports:

- inventory sync from a public dataset
- inventory normalization and validation
- promotion history tracking
- rule-based and AI-assisted generation
- platform-specific formatting for Instagram, Facebook, and X
- per-run AI budget guards
- X approval workflow
- dry-run and live publishing to X
- a local dashboard for previews and usage metrics

The main missing pieces are:

- generic multi-platform publishing architecture
- shirt-level promotion allow/block controls
- a daily planner or scheduler layer
- deployment and long-running host operations
- audience targeting and demographic modeling
- performance feedback and optimization loops

## Recommended Implementation Order

1. Multi-platform publishing foundation
2. Promotion eligibility and suppression controls
3. Daily planner with posting and AI budget caps
4. Deployment and persistent host operations
5. Audience modeling and targeted copy
6. Trend inputs and closed-loop optimization

## Phase 1: Multi-Platform Foundation

Goal: stop treating X as a special case and create one publishing model that can support multiple platforms cleanly.

### Deliverables

- Define a shared internal post model used across all platforms.
- Introduce a platform adapter interface for generation and publishing behavior.
- Move X publishing into a platform adapter module.
- Add placeholder or partial adapters for:
  - Instagram
  - Facebook
  - Bluesky
- Separate platform generation support from live publishing support.
- Add a publish queue/state model that tracks:
  - platform
  - status
  - source batch
  - scheduled time
  - approval state
  - external post ID

### Suggested Repo Changes

- Add `bot/publishers/`
- Move X-specific logic from `bot/x_publisher.py` into `bot/publishers/x.py`
- Add a generic publish entrypoint
- Add shared platform capability/config loading

### Notes

- Day one does not require live publishing for every platform.
- It is acceptable for Instagram and Facebook to begin as generation/approval/export targets only.

## Phase 2: Promotion Eligibility Controls

Goal: allow human judgment to override raw inventory selection.

### Deliverables

- Add a local overlay file for promotion decisions, separate from the synced inventory.
- Support shirt-level controls such as:
  - `promotable`
  - `promotion_priority`
  - `blocked_platforms`
  - `blocked_reasons`
  - `allowed_audiences`
- Filter selection through these overrides before generation.
- Add room for theme-level defaults and shirt-level overrides.

### Suggested Data Model

Use a local file such as:

`data/promotion_overrides.json`

Example shape:

```json
{
  "shirts": {
    "5d89cc30f937647d81ffc564": {
      "promotable": true,
      "promotion_priority": 3,
      "blocked_platforms": ["facebook"],
      "allowed_audiences": ["religion", "deadpan-humor"]
    },
    "bad-shirt-id": {
      "promotable": false,
      "blocked_reasons": ["weak design", "not brand-fit"]
    }
  }
}
```

### Notes

- Keep this overlay local to ShirtClawd; do not push merchandising opinion back into the canonical inventory sync source.
- This phase should happen before autonomous audience targeting.

## Phase 3: Daily Planner and Budget Controls

Goal: make posting decisions at the day level, not only at individual generation time.

### Deliverables

- Add a planner layer that decides:
  - how many posts to create today
  - which platforms to target
  - which shirts to use
  - whether to use rule-based or AI generation
- Enforce daily limits for:
  - max posts
  - max AI calls
  - max tokens
  - max estimated spend
- Reserve AI budget for higher-priority shirts or platforms.
- Produce a planning artifact that can be reviewed before publishing.

### Suggested Output

Add a file such as:

`output/daily_plan_YYYY-MM-DD.json`

The plan should list chosen shirts, platforms, generation mode, and estimated spend before any live publish step.

### Notes

- Existing per-run budget guards are useful, but they are not enough on their own.
- Budget enforcement should sit above generation in a planner, not only inside generation.

## Phase 4: Deployment and Persistent Host Operations

Goal: make ClawdBot run reliably on a dedicated machine without manual babysitting.

### Deliverables

- Define the production runtime for a small always-on host such as an old laptop.
- Add a repeatable deploy setup for code checkout, Python environment, and config loading.
- Run generation, planning, approval, and publish jobs through OS-level scheduling or a long-running service.
- Ensure the process starts automatically after reboot.
- Store state, logs, queues, outputs, and snapshots in stable local paths that survive restarts.
- Load API secrets safely at boot without depending on an interactive shell session.
- Add basic health monitoring so failures are visible.
- Add backup guidance for state files and logs.

### Suggested Host Setup

- Python virtual environment for dependencies
- `launchd` on macOS or `systemd` on Linux for persistent services
- cron or scheduled jobs for daily planning and publishing windows
- a dedicated logs directory
- a small deploy/runbook in the repo

### Notes

- This phase is what turns the bot from a project you run manually into a service that stays alive.
- Hosting should happen after the planner exists, so the deployed system has clear daily behavior to execute.
- The first-pass Mac laptop deployment plan lives in `MAC_HOSTING_PLAN.md`.

## Phase 5: Audience Modeling and Targeted Copy

Goal: move from generic posting to audience-aware posting.

### Deliverables

- Define an audience taxonomy for the catalog.
- Score shirts against one or more audiences.
- Score platform fit by audience.
- Generate audience-specific copy variants.
- Store audience choice in generated post artifacts.

### Initial Audience Examples

- regional pride
- sports fans
- transit nerds
- movie-reference people
- religious humor
- deadpan / absurdist humor

### Notes

- Start with deterministic audience matching from tags, theme, sub-theme, and overrides.
- Do not start with AI trend hunting here. First build a clean, explainable audience model.

## Phase 6: Trends and Optimization

Goal: improve targeting decisions using external signals and internal performance history.

### Deliverables

- Add internal performance storage for published posts.
- Track dimensions such as:
  - shirt
  - platform
  - audience
  - copy style
  - publish time
  - engagement outcome
- Add optional trend inputs such as:
  - seasonal calendar
  - sports calendar
  - holidays
  - cultural moments
- Use those signals to prioritize what gets generated and published.

### Notes

- This is the last phase for a reason.
- Without historical performance data, “optimize marketing dollar” is mostly guesswork.

## Proposed Architecture Direction

One reasonable target structure is:

```text
bot/
  ai_writer.py
  approval_queue.py
  audience.py
  data_loader.py
  eligibility.py
  inventory_sync.py
  planner.py
  post_generator.py
  publish_queue.py
  publishers/
    x.py
    bluesky.py
    instagram.py
    facebook.py
  selector.py
  usage_logger.py
  writer.py
```

This keeps the system split into:

- data ingestion
- eligibility rules
- planning
- generation
- publishing
- logging and metrics

## Milestone Definitions

### Milestone 1

ClawdBot can generate for multiple platforms using a shared post model, and publishing logic is no longer hardcoded around X.

### Milestone 2

ClawdBot respects explicit human merchandising controls for whether a shirt should be promoted.

### Milestone 3

ClawdBot can build and enforce a daily posting plan with hard limits on content volume and AI cost.

### Milestone 4

ClawdBot can run persistently on a dedicated host with automatic restart, scheduled jobs, and durable local state.

### Milestone 5

ClawdBot can target specific audiences with platform-aware copy.

### Milestone 6

ClawdBot can use performance history and trends to prioritize what gets posted.

## Near-Term Recommendation

If we are choosing only one immediate work stream, it should be:

1. add promotion override support
2. refactor publishing into platform adapters
3. add a daily planning layer
4. package deployment for the dedicated host

That sequence creates a stable base for everything else.

## Open Questions

These should be resolved before or during Phase 1 and Phase 2:

- Which platforms do we want to support as generation targets first?
- Which platforms do we want to support for live publishing first?
- Do we want approval to remain platform-specific, or become one shared review queue?
- Should “do not promote” live only in a local overlay, or also in the upstream product data at some point?
- What is the first pass at audience taxonomy?
- What daily budget should we optimize within?

## Out of Scope for Early Phases

The following should not block Phase 1 through Phase 3:

- sophisticated demographic inference
- real-time trend detection
- engagement scraping from third-party APIs
- automated experimentation or bandit-style optimization
- image generation or image editing

Those belong after the core system can reliably choose, generate, and publish the right content within budget.
