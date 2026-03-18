# ClawdBot Mac Hosting Plan

This document defines the first hosted version of ClawdBot for an old Mac laptop.

The goal is a small, reliable setup that can run every day without manual babysitting.

## Hosted V1 Scope

Hosted v1 should do only the following:

1. Build a daily plan from the current local inventory and promotion rules.
2. Generate posts for the chosen platforms.
3. Queue anything that requires approval.
4. Publish only posts that are approved and scheduled to go out.
5. Write logs and run summaries so failures are visible.

Hosted v1 should not depend on scheduled inventory sync.

Inventory sync remains a manual maintenance task because the catalog changes infrequently.

## Daily Workflow

The daily lifecycle on the Mac host is:

1. Morning planner job
2. Generation job
3. Approval waiting period
4. Scheduled publish job
5. Logging and summary output

In plain English: plan, generate, wait, publish, log.

## Pre-Laptop Decisions

Before the laptop is ready, we should decide:

- which platforms are included in hosted v1
- which platforms can publish live in hosted v1
- which posts require approval before publishing
- what the daily posting and AI budget limits are
- where local-only config and state should live on the host

## Required Product Work Before Hosting

These repo features should exist before the Mac host setup is considered complete:

1. Promotion override support
2. Daily planner support
3. Shared publishing flow that is not hardcoded around X
4. Basic deployment/runbook files for macOS

## Required Host Setup

The Mac laptop needs:

1. The repo cloned locally
2. Python and a virtual environment
3. A repeatable way to load secrets
4. Stable local paths for `data/`, `output/`, and logs
5. `launchd` jobs for scheduled runs
6. Automatic restart behavior after reboot
7. SSH access for remote management
8. Simple backups for state and logs

## Suggested Scheduled Jobs

Hosted v1 should start with a very small set of jobs:

1. Planner job once each morning
2. Generation job after planning
3. Publish job on one or more daily publish windows

Approval is not a scheduled generator job. It is a human review step between generation and publish.

## Operational Rules

- Keep inventory sync manual unless the business need changes.
- Prefer fewer scheduled jobs over a complicated orchestration layer.
- Fail safely: if approval is missing, do not publish.
- Keep logs and outputs on disk so runs can be inspected later.
- Treat the Mac as a durable local host, not a disposable machine.

## Definition of Done for Hosted V1

Hosted v1 is ready when:

1. The Mac reboots and ClawdBot scheduled jobs still run.
2. The planner creates a daily plan automatically.
3. Generation writes post batches automatically.
4. Approved posts publish on schedule.
5. Failed runs leave clear logs.
6. A human can SSH in and inspect or recover the system.
