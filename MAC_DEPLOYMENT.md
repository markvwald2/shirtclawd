# ClawdBot Mac Deployment

This is the practical setup for running ClawdBot on an old Mac laptop.

## Included Files

- `scripts/run_daily_workflow.sh`
- `scripts/publish_approved_x.sh`
- `publish_approved_x_queue.py`
- `launchd/com.shirtclawd.daily-workflow.plist`
- `launchd/com.shirtclawd.publish-approved-x.plist`
- `.env.example`

## Intended Workflow

1. `run_daily_workflow.sh` builds the daily plan and generates the planned posts.
2. Approved X posts can be published later by `publish_approved_x.sh`.
3. Both scripts write to the repo-local `logs/` directory through `launchd`.

## Host Setup

1. Clone the repo to the Mac.
2. Create a virtual environment:

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
```

3. Copy `.env.example` to `.env` and fill in real secrets.
   Use a Bluesky app password, not your main account password.
4. Make the scripts executable:

```bash
chmod +x scripts/run_daily_workflow.sh scripts/publish_approved_x.sh
```

5. Test the daily workflow manually:

```bash
scripts/run_daily_workflow.sh
```

6. Copy the `launchd` plist files into `~/Library/LaunchAgents/`.
7. Update the plist paths if the repo lives somewhere else on the Mac.
8. Load the jobs:

```bash
launchctl unload ~/Library/LaunchAgents/com.shirtclawd.daily-workflow.plist 2>/dev/null || true
launchctl unload ~/Library/LaunchAgents/com.shirtclawd.publish-approved-x.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.shirtclawd.daily-workflow.plist
launchctl load ~/Library/LaunchAgents/com.shirtclawd.publish-approved-x.plist
```

## Default Schedule

- Daily workflow: 9:00 AM local time
- Approved X publish window: 3:00 PM local time

These are starter defaults only. You can change the `Hour` and `Minute` values in the plist files later.

## Notes

- The scripts automatically source `.env` if it exists.
- The scripts assume the Python interpreter is `.venv/bin/python3`.
- Inventory sync is intentionally not part of the scheduled workflow.
- The X publish job reads the approval queue and skips anything already published.
- Bluesky live publishing is available through `publish_to_bluesky.py` and uses `BLUESKY_HANDLE` plus `BLUESKY_APP_PASSWORD`.
