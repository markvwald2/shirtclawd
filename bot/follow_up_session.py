import json
import os
import re
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from bot.bluesky_inbox import BlueskyInboxError, fetch_bluesky_inbox_items
from bot.follow_up import (
    automation_executable_actions,
    build_follow_up_actions,
    build_follow_up_brief,
    discover_follow_up_targets,
    is_api_executable_action,
    list_follow_up_actions,
    load_daily_plan,
    load_posts_for_plan,
    load_publish_records,
    merge_follow_up_actions,
    table_cell,
    write_follow_up_brief,
)
from bot.follow_up_executor import execute_approved_actions


DEFAULT_FOLLOW_UP_SESSION_STATE_PATH = Path("data/follow_up_session_state.json")
DEFAULT_SESSION_REPORT_PREFIX = "follow_up_session"
DEFAULT_INBOX_LOOKBACK_HOURS = 24
PENDING_FOLLOW_UP_STATUSES = ("drafted", "approved")


def run_follow_up_session(
    run_date,
    plan_path,
    output_dir=Path("output"),
    log_dir=Path("data"),
    queue_path=Path("data/follow_up_action_queue.json"),
    state_path=DEFAULT_FOLLOW_UP_SESSION_STATE_PATH,
    uptime_minutes=60,
    skip_target_discovery=False,
    target_candidates=3,
    target_search_limit=20,
    target_max_age_days=21,
    inbox_limit=50,
    inbox_lookback_hours=DEFAULT_INBOX_LOOKBACK_HOURS,
    execute_approved=False,
    publish=False,
    execute_platform=None,
    execute_limit=3,
    automation_only=False,
    now=None,
    fetch_inbox_items_fn=None,
    execute_approved_fn=None,
):
    started_at = coerce_datetime(now) or datetime.now(timezone.utc)
    started_iso = started_at.isoformat()
    state = load_follow_up_session_state(state_path)
    since = session_since_timestamp(state, started_at, lookback_hours=inbox_lookback_hours)

    plan = load_daily_plan(plan_path)
    post_refs = load_posts_for_plan(plan, output_dir)
    platforms = [entry.get("platform") for entry in plan.get("planned_posts", []) if entry.get("platform")]
    publish_records = load_publish_records(run_date, log_dir, platforms=platforms)

    target_discovery = {}
    if not skip_target_discovery:
        target_discovery = discover_follow_up_targets(
            post_refs=post_refs,
            run_date=run_date,
            max_candidates_per_post=target_candidates,
            search_limit=target_search_limit,
            max_age_days=target_max_age_days,
            exclude_handles=[os.getenv("BLUESKY_HANDLE")],
            exclude_threads_usernames=[os.getenv("THREADS_USERNAME"), os.getenv("THREADS_USER_ID")],
        )

    planned_actions_all = build_follow_up_actions(
        plan=plan,
        post_refs=post_refs,
        publish_records=publish_records,
        run_date=run_date,
        generated_at=started_iso,
        target_discovery=target_discovery,
    )
    planned_actions = automation_executable_actions(planned_actions_all) if automation_only else planned_actions_all

    inbox_items = []
    inbox_error = ""
    try:
        inbox_items = (fetch_inbox_items_fn or fetch_bluesky_inbox_items)(
            since=since,
            limit=inbox_limit,
        )
    except (BlueskyInboxError, RuntimeError, ValueError) as exc:
        inbox_error = str(exc)

    inbox_actions = build_inbox_follow_up_actions(
        run_date=run_date,
        inbox_items=inbox_items,
        generated_at=started_iso,
    )

    merge_follow_up_actions(
        planned_actions + inbox_actions,
        path=queue_path,
        replace_run_date=run_date if automation_only else None,
    )

    execution_results = []
    if execute_approved:
        executor = execute_approved_fn or execute_approved_actions
        execution_results = executor(
            queue_path=queue_path,
            dry_run=not publish,
            platform=execute_platform,
            limit=execute_limit,
            run_date=run_date,
        )

    queue_actions = list_follow_up_actions(queue_path, run_date=run_date)
    carryover_actions = [
        action
        for action in list_follow_up_actions(queue_path)
        if is_pending_follow_up_action(action) and is_prior_run_date(action.get("date"), run_date)
    ]
    follow_up_markdown = build_follow_up_brief(
        plan=plan,
        post_refs=post_refs,
        publish_records=publish_records,
        run_date=run_date,
        uptime_minutes=uptime_minutes,
        generated_at=started_iso,
        queue_actions=queue_actions,
    )
    follow_up_brief_path = write_follow_up_brief(follow_up_markdown, run_date, output_dir)

    finished_at = datetime.now(timezone.utc)
    summary = summarize_session(
        run_date=run_date,
        since=since,
        started_at=started_iso,
        finished_at=finished_at.isoformat(),
        planned_actions=planned_actions,
        suppressed_planned_action_count=max(0, len(planned_actions_all) - len(planned_actions)),
        inbox_items=inbox_items,
        inbox_actions=inbox_actions,
        inbox_error=inbox_error,
        queue_actions=queue_actions,
        execution_results=execution_results,
        target_discovery=target_discovery,
        carryover_actions=carryover_actions,
    )
    session_report = build_follow_up_session_report(summary, queue_actions, carryover_actions=carryover_actions)
    session_report_path = write_follow_up_session_report(session_report, run_date, output_dir)

    checked_at_for_state = finished_at.isoformat() if not inbox_error else since
    record_follow_up_session_state(
        state_path,
        checked_at=checked_at_for_state,
        run_date=run_date,
        summary=summary,
    )

    return {
        **summary,
        "follow_up_brief_path": str(follow_up_brief_path),
        "session_report_path": str(session_report_path),
        "queue_path": str(queue_path),
    }


def build_inbox_follow_up_actions(run_date, inbox_items, generated_at=None):
    generated = generated_at or datetime.now(timezone.utc).isoformat()
    actions = []
    for item in inbox_items:
        target_url = item.get("url") or item.get("uri") or ""
        if not target_url:
            continue
        action_id = inbox_action_id(run_date, item)
        actions.append(
            {
                "action_id": action_id,
                "date": run_date,
                "kind": "reply_comment",
                "status": "drafted",
                "platform": "bluesky",
                "shirt_id": "",
                "title": f"Bluesky {item.get('reason', 'notification')} from {item.get('author_handle', '')}",
                "content_goal": "respond",
                "cta_goal": "conversation",
                "source_file": "bluesky_notifications",
                "published_id": item.get("reason_subject", ""),
                "target_url": target_url,
                "target_uri": item.get("uri", ""),
                "target_author_handle": item.get("author_handle", ""),
                "target_author_display_name": item.get("author_display_name", ""),
                "target_reason": inbox_target_reason(item),
                "target_created_at": item.get("indexed_at", ""),
                "target_score": inbox_score(item),
                "target_metrics": {},
                "draft_text": build_inbox_reply_draft(item),
                "approved_text": "",
                "notification_reason": item.get("reason", ""),
                "notification_text": item.get("text", ""),
                "human_gate": "Review the inbound context and approve before replying publicly.",
                "created_at": generated,
                "updated_at": generated,
                "notes": [],
            }
        )
    return actions


def inbox_action_id(run_date, item):
    token = rkey_from_at_uri(item.get("uri")) or stable_token(item.get("uri") or item.get("url") or item.get("indexed_at"))
    return f"FU-{run_date}-IN-{token}"


def build_inbox_reply_draft(item):
    reason = item.get("reason")
    if reason == "mention":
        return "We have been summoned, and we accept the assignment."
    if reason == "quote":
        return "This is now part of the public record, unfortunately."
    return "Fair. The official position is mostly that the argument deserves merchandise."


def inbox_target_reason(item):
    author = item.get("author_display_name") or item.get("author_handle") or "someone"
    reason = item.get("reason") or "notification"
    text = item.get("text") or ""
    suffix = f": {text}" if text else ""
    return f"Inbound Bluesky {reason} from {author}{suffix}"


def inbox_score(item):
    reason = item.get("reason")
    if reason in ("reply", "mention"):
        return 90
    if reason == "quote":
        return 80
    return 50


def summarize_session(
    run_date,
    since,
    started_at,
    finished_at,
    planned_actions,
    suppressed_planned_action_count,
    inbox_items,
    inbox_actions,
    inbox_error,
    queue_actions,
    execution_results,
    target_discovery,
    carryover_actions=None,
):
    status_counts = Counter(action.get("status", "unknown") for action in queue_actions)
    carryover_actions = list(carryover_actions or [])
    carryover_status_counts = Counter(action.get("status", "unknown") for action in carryover_actions)
    approved_supported = [
        action
        for action in queue_actions
        if action.get("status") == "approved"
        and is_api_executable_action(action)
    ]
    approved_manual = [
        action
        for action in queue_actions
        if action.get("status") == "approved" and action not in approved_supported
    ]
    discovery_candidate_count = sum(
        len(result.get("candidates", []))
        for result in target_discovery.values()
        if isinstance(result, dict)
    )
    discovery_error_count = sum(
        1 for result in target_discovery.values() if isinstance(result, dict) and result.get("error")
    )
    return {
        "run_date": run_date,
        "started_at": started_at,
        "finished_at": finished_at,
        "checked_since": since,
        "planned_action_count": len(planned_actions),
        "suppressed_planned_action_count": suppressed_planned_action_count,
        "inbox_item_count": len(inbox_items),
        "inbox_action_count": len(inbox_actions),
        "inbox_error": inbox_error,
        "queue_status_counts": dict(sorted(status_counts.items())),
        "carryover_status_counts": dict(sorted(carryover_status_counts.items())),
        "carryover_pending_count": len(carryover_actions),
        "approved_supported_count": len(approved_supported),
        "approved_manual_count": len(approved_manual),
        "execution_results": execution_results,
        "execution_sent_count": sum(1 for result in execution_results if result.get("status") == "sent"),
        "execution_dry_run_count": sum(1 for result in execution_results if result.get("status") == "dry_run"),
        "execution_error_count": sum(1 for result in execution_results if result.get("status") == "error"),
        "discovery_candidate_count": discovery_candidate_count,
        "discovery_error_count": discovery_error_count,
    }


def build_follow_up_session_report(summary, queue_actions, carryover_actions=None):
    carryover_actions = list(carryover_actions or [])
    lines = [
        f"# ShirtClawd Daily Follow-Up Session - {summary['run_date']}",
        "",
        f"Started: {summary['started_at']}",
        f"Finished: {summary['finished_at']}",
        f"Checked since: {summary['checked_since']}",
        "",
        "## Catch-Up Summary",
        "",
        f"- Planned outreach actions refreshed: {summary['planned_action_count']}",
        f"- Manual-only planned actions suppressed: {summary.get('suppressed_planned_action_count', 0)}",
        f"- New Bluesky inbox items found: {summary['inbox_item_count']}",
        f"- Inbox reply drafts queued: {summary['inbox_action_count']}",
        f"- Discovery candidates found: {summary['discovery_candidate_count']}",
        f"- Carryover drafted/approved actions: {summary.get('carryover_pending_count', 0)}",
        f"- Approved API-safe actions still ready: {summary['approved_supported_count']}",
        f"- Approved manual/unsupported actions still ready: {summary['approved_manual_count']}",
    ]
    if summary.get("inbox_error"):
        lines.append(f"- Bluesky inbox check unavailable: {summary['inbox_error']}")
    if summary.get("discovery_error_count"):
        lines.append(f"- Discovery had {summary['discovery_error_count']} platform error(s); see the main follow-up brief.")

    lines.extend(
        [
            "",
            "## Queue Counts",
            "",
            "| Status | Count |",
            "| --- | --- |",
        ]
    )
    for status, count in summary.get("queue_status_counts", {}).items():
        lines.append(f"| {table_cell(status)} | {count} |")

    lines.extend(
        [
            "",
            "## Executed This Session",
            "",
        ]
    )
    execution_results = summary.get("execution_results") or []
    if not execution_results:
        lines.append("- No approved actions were executed in this session.")
    else:
        for result in execution_results:
            detail = result.get("external_action_id") or result.get("reason") or result.get("target_url") or ""
            lines.append(f"- `{result.get('action_id')}` [{result.get('status')}]: {detail}")

    lines.extend(
        [
            "",
            "## Carryover Backlog",
            "",
        ]
    )
    if not carryover_actions:
        lines.append("- No drafted or approved follow-up actions from prior dates.")
    else:
        for action in carryover_actions:
            lines.append(format_follow_up_action_line(action, include_date=True))

    pending = [
        action
        for action in queue_actions
        if is_pending_follow_up_action(action)
    ]
    lines.extend(
        [
            "",
            "## Current To-Dos",
            "",
        ]
    )
    if not pending:
        lines.append("- No drafted or approved follow-up actions remain.")
    else:
        for action in pending:
            lines.append(format_follow_up_action_line(action))

    lines.extend(
        [
            "",
            "## Tomorrow Handoff",
            "",
            "- Review drafted inbox replies first.",
            "- Execute approved API-safe replies with `python follow_up.py --daily-session --session-execute-approved --publish`.",
            "- Automation-only mode leaves manual-only opportunities out of the queue.",
            "",
        ]
    )
    return "\n".join(lines)


def is_pending_follow_up_action(action):
    return action.get("status") in PENDING_FOLLOW_UP_STATUSES


def is_prior_run_date(action_date, run_date):
    if not action_date:
        return False
    return str(action_date) < str(run_date)


def format_follow_up_action_line(action, include_date=False):
    label = (
        action.get("target_author_display_name")
        or action.get("target_author_handle")
        or action.get("target_type")
        or action.get("title")
        or action.get("action_id")
    )
    date_part = f" ({action.get('date')})" if include_date and action.get("date") else ""
    target = action.get("target_url") or action.get("target_search_url") or ""
    target_part = f" -> {target}" if target else ""
    return (
        f"- `{action.get('action_id')}`{date_part} [{action.get('status')}] "
        f"{action.get('platform')} {action.get('kind')} {table_cell(label)}{target_part}"
    )


def write_follow_up_session_report(markdown, run_date, output_dir=Path("output")):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    destination = output_path / f"{DEFAULT_SESSION_REPORT_PREFIX}_{run_date}.md"
    destination.write_text(markdown)
    return destination


def load_follow_up_session_state(path=DEFAULT_FOLLOW_UP_SESSION_STATE_PATH):
    state_path = Path(path)
    if not state_path.exists():
        return {"sessions": []}
    try:
        with state_path.open() as handle:
            payload = json.load(handle)
    except json.JSONDecodeError:
        return {"sessions": []}
    if not isinstance(payload, dict):
        return {"sessions": []}
    payload.setdefault("sessions", [])
    if not isinstance(payload["sessions"], list):
        payload["sessions"] = []
    return payload


def save_follow_up_session_state(state, path=DEFAULT_FOLLOW_UP_SESSION_STATE_PATH):
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=state_path.parent, delete=False) as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(state_path)


def session_since_timestamp(state, now, lookback_hours=DEFAULT_INBOX_LOOKBACK_HOURS):
    last_checked = state.get("last_checked_at")
    if last_checked:
        return last_checked
    fallback = now - timedelta(hours=max(1, int(lookback_hours or DEFAULT_INBOX_LOOKBACK_HOURS)))
    return fallback.isoformat()


def record_follow_up_session_state(path, checked_at, run_date, summary):
    state = load_follow_up_session_state(path)
    state["last_checked_at"] = checked_at
    state["last_run_date"] = run_date
    compact_summary = {
        "run_date": run_date,
        "checked_at": checked_at,
        "inbox_item_count": summary.get("inbox_item_count", 0),
        "inbox_action_count": summary.get("inbox_action_count", 0),
        "execution_sent_count": summary.get("execution_sent_count", 0),
        "queue_status_counts": summary.get("queue_status_counts", {}),
    }
    sessions = state.setdefault("sessions", [])
    sessions.append(compact_summary)
    state["sessions"] = sessions[-14:]
    save_follow_up_session_state(state, path)


def coerce_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def rkey_from_at_uri(uri):
    parsed = urlparse(str(uri or ""))
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.scheme == "at" and len(parts) == 2:
        return safe_token(parts[1])
    return ""


def stable_token(value):
    token = safe_token(value)
    return token[:24] or "unknown"


def safe_token(value):
    return re.sub(r"[^A-Za-z0-9_-]+", "-", str(value or "")).strip("-")
