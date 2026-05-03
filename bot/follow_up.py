import json
import re
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from bot.bluesky_discovery import BlueskyDiscoveryError, find_reply_candidates as find_bluesky_reply_candidates
from bot.facebook_discovery import find_reply_candidates as find_facebook_reply_candidates
from bot.instagram_discovery import (
    InstagramDiscoveryError,
    build_hashtags as build_instagram_hashtags,
    find_reply_candidates as find_instagram_reply_candidates,
    manual_hashtag_candidates as manual_instagram_hashtag_candidates,
)
from bot.threads_discovery import (
    ThreadsDiscoveryError,
    find_reply_candidates as find_threads_reply_candidates,
    manual_search_candidates as manual_threads_search_candidates,
)


PUBLISH_LOG_FILENAMES = {
    "bluesky": "bluesky_publish_log.jsonl",
    "facebook": "facebook_publish_log.jsonl",
    "instagram": "instagram_publish_log.jsonl",
    "threads": "threads_publish_log.jsonl",
    "x": "x_publish_log.jsonl",
}

DEFAULT_FOLLOW_UP_QUEUE_PATH = Path("data/follow_up_action_queue.json")
ACTION_STATUSES = ("drafted", "approved", "sent", "skipped")
PENDING_ACTION_STATUSES = ("drafted", "approved")
DEFAULT_CARRYOVER_MAX_DAYS = 1
DAILY_PLAN_FILENAME_RE = re.compile(r"^daily_plan_(\d{4}-\d{2}-\d{2})(?:[_-].*)?\.json$")

EXTERNAL_ID_KEYS = (
    "uri",
    "instagram_media_id",
    "facebook_post_id",
    "threads_media_id",
    "tweet_id",
    "post_id",
    "id",
)


def find_latest_daily_plan(output_dir=Path("output"), before_date=None, by_mtime=False):
    output_path = Path(output_dir)
    if not output_path.exists():
        return None

    cutoff_day = parse_action_day(before_date)
    candidates = []
    for path in output_path.glob("daily_plan_*.json"):
        if not path.is_file():
            continue
        plan_date = daily_plan_date_for_path(path)
        plan_day = parse_action_day(plan_date)
        if not plan_day:
            continue
        if cutoff_day and plan_day >= cutoff_day:
            continue
        try:
            mtime = path.stat().st_mtime_ns
        except OSError:
            mtime = 0
        date_key = plan_day.isoformat()
        sort_key = (mtime, date_key, path.name) if by_mtime else (date_key, mtime, path.name)
        candidates.append((sort_key, path))

    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def daily_plan_date_for_path(path):
    plan_path = Path(path)
    filename_match = DAILY_PLAN_FILENAME_RE.match(plan_path.name)
    filename_date = filename_match.group(1) if filename_match else ""

    try:
        with plan_path.open() as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return filename_date

    if isinstance(payload, dict):
        plan_date = payload.get("plan_date")
        if parse_action_day(plan_date):
            return str(plan_date)[:10]
    return filename_date


def build_follow_up_brief(
    plan,
    post_refs,
    publish_records,
    run_date,
    uptime_minutes=60,
    generated_at=None,
    queue_actions=None,
):
    generated = generated_at or datetime.now(timezone.utc).isoformat()
    campaign = plan.get("campaign") or "uncampaign"
    series = first_truthy([entry.get("series") for entry in plan.get("planned_posts", [])]) or campaign
    audience_lane = first_truthy([entry.get("audience_lane") for entry in plan.get("planned_posts", [])]) or "general"
    offer = first_truthy([entry.get("active_offer") for entry in plan.get("planned_posts", [])])
    offer_ends_on = first_truthy([entry.get("offer_ends_on") for entry in plan.get("planned_posts", [])])
    action_lookup = {action.get("action_id"): action for action in queue_actions or []}

    lines = [
        f"# ShirtClawd Follow-Up Brief - {run_date}",
        "",
        f"Generated: {generated}",
        f"Automation window: {uptime_minutes} minutes",
        "Mode: semi-automated drafts and checklist only. Publish replies, comments, DMs, follows, and offers only after human approval.",
        "",
        "## Campaign Snapshot",
        "",
        f"- Campaign: {campaign}",
        f"- Series: {series}",
        f"- Audience lane: {audience_lane}",
    ]
    if offer:
        suffix = f" through {offer_ends_on}" if offer_ends_on else ""
        lines.append(f"- Active offer: {offer}{suffix}")
    lines.extend(
        [
            "- Distribution posture: borrow attention from Colorado conversations before asking for the sale.",
            "",
            "## Published Posts",
            "",
            "| Platform | Shirt | Goal | CTA | Published ID |",
            "| --- | --- | --- | --- | --- |",
        ]
    )

    matched_records = []
    for ref in post_refs:
        entry = ref["entry"]
        post = ref["post"]
        record = find_publish_record(post, entry, publish_records)
        matched_records.append(record)
        lines.append(
            "| {platform} | {title} | {goal} | {cta} | {external_id} |".format(
                platform=table_cell(entry.get("platform") or post.get("platform") or ""),
                title=table_cell(post.get("title") or entry.get("title") or ""),
                goal=table_cell(post.get("content_goal") or entry.get("content_goal") or ""),
                cta=table_cell(post.get("cta_goal") or entry.get("cta_goal") or ""),
                external_id=table_cell(external_id_for_record(record) if record else "not found"),
            )
        )

    lines.extend(
        [
            "",
            "## 60-Minute Follow-Up Queue",
            "",
            "| Window | Action | Semi-automated output | Human gate |",
            "| --- | --- | --- | --- |",
            "| 0-5 min | Sanity-check published posts. | Use the table above to open each platform and confirm media/caption rendered correctly. | Fix or delete anything broken before doing outreach. |",
            "| 5-25 min | Find conversations already talking about today's targets. | Use the discovery searches below. Save promising URLs/posts manually. | Only engage where the joke fits the existing conversation. |",
            "| 25-45 min | Draft replies/comments. | Use the reply drafts below as starting points. | Approve and lightly customize every public reply. |",
            "| 45-55 min | Seed creator/community outreach. | Use the outreach prompts below for 2-3 targets. | Do not DM or offer codes without approval. |",
            "| 55-60 min | Log early signals. | Fill the tracking table at the bottom. | Mark any surprise learning for tomorrow's planner. |",
            "",
            "## Action Queue Commands",
            "",
            "- List: `python follow_up.py --list-actions --date YYYY-MM-DD`",
            "- Approve: `python follow_up.py --approve ACTION_ID --target-url \"https://...\" --copy \"final text\"`",
            "- Mark sent: `python follow_up.py --mark-sent ACTION_ID --target-url \"https://...\"`",
            "- Skip: `python follow_up.py --skip ACTION_ID --note \"why\"`",
            "- Dry-run execution: `python follow_up.py --execute-approved --platform bluesky`",
            "- Publish approved Bluesky replies: `python follow_up.py --execute-approved --platform bluesky --publish --limit 3`",
            "",
            "## Discovery Searches",
            "",
            "Use these searches to find Colorado-native conversations and pages. Bluesky actions may already include candidate posts when network discovery succeeds.",
            "",
        ]
    )

    for ref in post_refs:
        entry = ref["entry"]
        post = ref["post"]
        title = post.get("title") or entry.get("title") or "Untitled"
        platform = entry.get("platform") or post.get("platform") or "platform"
        topic = extract_topic(title)
        lines.extend(
            [
                f"### {title} ({platform})",
                "",
            ]
        )
        for query in build_discovery_queries(topic):
            lines.append(f"- {query}")
        lines.append("")

    append_candidate_target_lines(lines, queue_actions or [])

    lines.extend(
        [
            "## Reply And Comment Drafts",
            "",
            "Use these as editable shells, not as auto-posted copy.",
            "",
        ]
    )
    for index, ref in enumerate(post_refs, start=1):
        entry = ref["entry"]
        post = ref["post"]
        title = post.get("title") or entry.get("title") or "Untitled"
        platform = entry.get("platform") or post.get("platform") or "platform"
        topic = extract_topic(title)
        goal = post.get("content_goal") or entry.get("content_goal") or ""
        cta = post.get("cta_goal") or entry.get("cta_goal") or ""
        lines.extend(
            [
                f"### FU-{run_date}-{index:02d}: {title} ({platform})",
                "",
                f"- Goal: {goal or 'conversation'}",
                f"- CTA: {cta or 'reply'}",
            ]
        )
        for draft_index, draft in enumerate(build_reply_drafts(topic, goal, cta, post), start=1):
            action_id = reply_action_id(run_date, index, draft_index)
            action = action_lookup.get(action_id, {})
            status = action.get("status", "drafted")
            text = action.get("approved_text") if status == "approved" and action.get("approved_text") else draft
            target = action.get("target_url")
            target_suffix = f" target: {target}" if target else ""
            lines.append(f"- `{action_id}` [{status}]{target_suffix}: {text}")
        lines.append("")

    lines.extend(
        [
            "## Creator And Community Outreach",
            "",
            "| ID | Status | Target type | How to find it | Approval-ready prompt |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for outreach_index, (target_type, search, prompt) in enumerate(build_outreach_rows(series), start=1):
        action_id = outreach_action_id(run_date, outreach_index)
        action = action_lookup.get(action_id, {})
        status = action.get("status", "drafted")
        text = action.get("approved_text") if status == "approved" and action.get("approved_text") else prompt
        lines.append(
            f"| `{table_cell(action_id)}` | {table_cell(status)} | {table_cell(target_type)} | {table_cell(search)} | {table_cell(text)} |"
        )

    lines.extend(
        [
            "",
            "## Performance Tracking",
            "",
            "Fill this during the final minutes of the uptime window, then again tomorrow if you want a 24-hour read.",
            "",
            "| Platform | Published ID | 1h replies/comments | 1h shares/reposts | 1h follows/clicks | 24h notes |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for ref, record in zip(post_refs, matched_records):
        platform = ref["entry"].get("platform") or ref["post"].get("platform") or ""
        lines.append(
            "| {platform} | {external_id} |  |  |  |  |".format(
                platform=table_cell(platform),
                external_id=table_cell(external_id_for_record(record) if record else "not found"),
            )
        )

    lines.extend(
        [
            "",
            "## Tomorrow Feedback",
            "",
            "- Best conversation starter:",
            "- Weakest post or angle:",
            "- New sacred cow nominations:",
            "- Creator/page worth revisiting:",
            "- One thing to change in tomorrow's campaign:",
            "",
        ]
    )
    return "\n".join(lines)


def build_follow_up_actions(plan, post_refs, publish_records, run_date, generated_at=None, target_discovery=None, automation_only=False):
    generated = generated_at or datetime.now(timezone.utc).isoformat()
    series = first_truthy([entry.get("series") for entry in plan.get("planned_posts", [])]) or plan.get("campaign") or ""
    discovered_targets = target_discovery or {}
    actions = []

    for post_index, ref in enumerate(post_refs, start=1):
        entry = ref["entry"]
        post = ref["post"]
        record = find_publish_record(post, entry, publish_records)
        platform = entry.get("platform") or post.get("platform") or ""
        title = post.get("title") or entry.get("title") or ""
        topic = extract_topic(title)
        goal = post.get("content_goal") or entry.get("content_goal") or ""
        cta = post.get("cta_goal") or entry.get("cta_goal") or ""
        group_id = reply_group_id(run_date, post_index)
        discovery_result = discovered_targets.get(group_id, {})
        candidates = discovery_result.get("candidates", []) if isinstance(discovery_result, dict) else []
        discovery_error = discovery_result.get("error", "") if isinstance(discovery_result, dict) else ""
        for draft_index, draft in enumerate(build_reply_drafts(topic, goal, cta, post), start=1):
            candidate = candidates[draft_index - 1] if draft_index <= len(candidates) else None
            action = {
                "action_id": reply_action_id(run_date, post_index, draft_index),
                "date": run_date,
                "kind": "reply_comment",
                "status": "drafted",
                "platform": platform,
                "shirt_id": entry.get("shirt_id") or post.get("shirt_id") or "",
                "title": title,
                "content_goal": goal,
                "cta_goal": cta,
                "source_file": ref.get("source_file", ""),
                "published_id": external_id_for_record(record) if record else "",
                "target_url": "",
                "draft_text": draft,
                "approved_text": "",
                "discovery_queries": build_discovery_queries(topic),
                "target_candidates": candidates,
                "human_gate": "Approve the candidate target and customize copy before posting publicly.",
                "created_at": generated,
                "updated_at": generated,
                "notes": [],
            }
            if candidate:
                apply_candidate_to_action(action, candidate)
            if discovery_error:
                action["target_discovery_error"] = discovery_error
            if not automation_only or is_api_executable_action(action):
                actions.append(action)

    if not automation_only:
        for outreach_index, (target_type, search, prompt) in enumerate(build_outreach_rows(series), start=1):
            actions.append(
                {
                    "action_id": outreach_action_id(run_date, outreach_index),
                    "date": run_date,
                    "kind": "outreach_dm",
                    "status": "drafted",
                    "platform": "manual",
                    "target_type": target_type,
                    "target_search": search,
                    "target_url": "",
                    "draft_text": prompt,
                    "approved_text": "",
                    "human_gate": "Approve target and copy before sending any DM or offer.",
                    "created_at": generated,
                    "updated_at": generated,
                    "notes": [],
                }
            )

    return actions


def apply_candidate_to_action(action, candidate):
    candidate_platform = candidate.get("platform") or action.get("platform")
    action["target_url"] = candidate.get("url", "")
    action["target_uri"] = candidate.get("uri", "")
    action["target_author_handle"] = candidate.get("author_handle", "")
    action["target_author_display_name"] = candidate.get("author_display_name", "")
    action["target_query"] = candidate.get("query", "")
    action["target_reason"] = candidate.get("reason", "")
    action["target_created_at"] = candidate.get("created_at", "")
    action["target_score"] = candidate.get("score", 0)
    action["target_metrics"] = {
        "likes": candidate.get("like_count", 0),
        "reposts": candidate.get("repost_count", 0),
        "replies": candidate.get("reply_count", 0),
        "comments": candidate.get("comment_count", 0),
        "quotes": candidate.get("quote_count", 0),
    }
    if candidate.get("target_search_url"):
        action["target_search_url"] = candidate["target_search_url"]
    if candidate.get("manual_review"):
        action["target_manual_review"] = True
    if not candidate.get("manual_review"):
        candidate_id = candidate.get("id") or candidate.get("uri") or ""
        if candidate_platform == "threads" and candidate_id:
            action["target_thread_id"] = candidate.get("target_thread_id") or candidate.get("target_media_id") or candidate_id
        elif candidate_platform == "facebook" and candidate_id:
            action["target_object_id"] = candidate.get("target_object_id") or candidate.get("target_post_id") or candidate_id
        elif candidate_platform == "instagram" and candidate.get("comment_id"):
            action["target_comment_id"] = candidate["comment_id"]
    for key in ("target_id", "target_object_id", "target_post_id", "target_thread_id", "target_media_id", "target_comment_id"):
        if candidate.get(key):
            action[key] = candidate[key]
    return action


def append_candidate_target_lines(lines, actions):
    targeted_actions = [
        action
        for action in actions
        if action.get("kind") == "reply_comment"
        and action.get("status") in ("drafted", "approved")
        and action.get("target_url")
    ]
    errors = [
        action
        for action in actions
        if action.get("kind") == "reply_comment" and action.get("target_discovery_error")
    ]
    if not targeted_actions and not errors:
        return

    lines.extend(
        [
            "## Candidate Targets",
            "",
            "Review these before approving; they are suggested conversation entries, not auto-posted actions.",
            "",
        ]
    )
    for action in targeted_actions:
        label = action.get("target_author_display_name") or action.get("target_author_handle") or action.get("target_url")
        platform = action.get("platform") or "platform"
        reason = action.get("target_reason") or f"Candidate selected by {platform} discovery."
        lines.append(
            f"- `{action.get('action_id')}` [{action.get('status', 'drafted')}]: "
            f"{table_cell(platform)} target [{table_cell(label)}]({action.get('target_url')}) - {reason}"
        )
        if action.get("target_search_url"):
            lines.append(f"  Search/review: {action.get('target_search_url')}")
    seen_errors = set()
    for action in errors:
        error = table_cell(action.get("target_discovery_error"))
        key = (action.get("platform"), error)
        if key in seen_errors:
            continue
        seen_errors.add(key)
        lines.append(
            f"- {table_cell(action.get('platform') or 'Platform')} discovery unavailable: {error}"
        )
    lines.append("")


def load_follow_up_queue(path=DEFAULT_FOLLOW_UP_QUEUE_PATH):
    queue_path = Path(path)
    if not queue_path.exists():
        return {"actions": []}
    try:
        with queue_path.open() as handle:
            payload = json.load(handle)
    except json.JSONDecodeError:
        return {"actions": []}
    if not isinstance(payload, dict) or not isinstance(payload.get("actions"), list):
        return {"actions": []}
    return payload


def save_follow_up_queue(queue, path=DEFAULT_FOLLOW_UP_QUEUE_PATH):
    queue_path = Path(path)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=queue_path.parent, delete=False) as handle:
        json.dump(queue, handle, indent=2)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(queue_path)


def merge_follow_up_actions(actions, path=DEFAULT_FOLLOW_UP_QUEUE_PATH, replace_run_date=None, cleanup_backlog=True):
    queue = load_follow_up_queue(path)
    existing = {action.get("action_id"): action for action in queue.get("actions", [])}
    merged = []
    seen = set()
    for action in actions:
        action_id = action["action_id"]
        preserved = existing.get(action_id, {})
        merged_action = dict(action)
        if preserved:
            merged_action["created_at"] = preserved.get("created_at") or action.get("created_at")
            status = preserved.get("status", "drafted")
            if status in ACTION_STATUSES:
                merged_action["status"] = status
            for key in (
                "approved_at",
                "approved_text",
                "sent_at",
                "skipped_at",
                "external_action_id",
                "notes",
            ):
                if key in preserved:
                    merged_action[key] = preserved[key]
            preserve_target = status in ("approved", "sent", "skipped")
            if preserve_target:
                preserve_target_metadata = target_metadata_matches_url(preserved)
                target_id_keys = {
                    "target_id",
                    "target_object_id",
                    "target_post_id",
                    "target_thread_id",
                    "target_media_id",
                    "target_comment_id",
                }
                for key in (
                    "target_url",
                    "target_author_handle",
                    "target_author_display_name",
                    "target_uri",
                    "target_query",
                    "target_reason",
                    "target_created_at",
                    "target_score",
                    "target_metrics",
                    "target_search_url",
                    "target_manual_review",
                    "target_id",
                    "target_object_id",
                    "target_post_id",
                    "target_thread_id",
                    "target_media_id",
                    "target_comment_id",
                ):
                    if key in preserved:
                        if key == "target_url" or key in target_id_keys or preserve_target_metadata:
                            merged_action[key] = preserved[key]
                        else:
                            merged_action.pop(key, None)
                    elif key != "target_url":
                        merged_action.pop(key, None)
        merged.append(merged_action)
        seen.add(action_id)

    for action in queue.get("actions", []):
        if action.get("action_id") in seen:
            continue
        if replace_run_date and action.get("date") == replace_run_date:
            continue
        merged.append(action)

    merged.sort(key=lambda item: item.get("action_id", ""))
    queue["actions"] = merged
    if cleanup_backlog:
        cleanup_follow_up_queue(
            queue,
            reference_date=latest_action_date(actions) or latest_action_date(merged),
        )
    save_follow_up_queue(queue, path)
    return queue


def cleanup_follow_up_backlog(path=DEFAULT_FOLLOW_UP_QUEUE_PATH, reference_date=None, max_carryover_days=DEFAULT_CARRYOVER_MAX_DAYS):
    queue = load_follow_up_queue(path)
    summary = cleanup_follow_up_queue(
        queue,
        reference_date=reference_date or latest_action_date(queue.get("actions", [])),
        max_carryover_days=max_carryover_days,
    )
    save_follow_up_queue(queue, path)
    return summary


def cleanup_follow_up_queue(queue, reference_date=None, max_carryover_days=DEFAULT_CARRYOVER_MAX_DAYS, now=None):
    reference_day = parse_action_day(reference_date)
    skipped_duplicate = 0
    skipped_stale = 0
    timestamp = now or datetime.now(timezone.utc).isoformat()

    pending_by_key = {}
    for action in queue.get("actions", []):
        key = follow_up_backlog_key(action)
        if not key:
            continue
        current = pending_by_key.get(key)
        if current is None or backlog_keep_sort_key(action) > backlog_keep_sort_key(current):
            pending_by_key[key] = action

    keep_ids = {action.get("action_id") for action in pending_by_key.values()}
    for action in queue.get("actions", []):
        if not follow_up_backlog_key(action):
            continue
        if action.get("action_id") in keep_ids:
            continue
        skip_pending_action(
            action,
            timestamp=timestamp,
            note="Skipped as a duplicate manual follow-up target; kept the newest pending action for this target.",
        )
        skipped_duplicate += 1

    if reference_day:
        cutoff = reference_day - timedelta(days=max(0, int(max_carryover_days)))
        for action in queue.get("actions", []):
            if not follow_up_backlog_key(action):
                continue
            action_day = parse_action_day(action.get("date"))
            if action_day and action_day < cutoff:
                skip_pending_action(
                    action,
                    timestamp=timestamp,
                    note=f"Skipped as stale manual follow-up carryover older than {max_carryover_days} day(s).",
                )
                skipped_stale += 1

    return {
        "skipped_duplicate_count": skipped_duplicate,
        "skipped_stale_count": skipped_stale,
        "reference_date": reference_day.isoformat() if reference_day else "",
        "max_carryover_days": max_carryover_days,
    }


def follow_up_backlog_key(action):
    if action.get("status") not in PENDING_ACTION_STATUSES:
        return None
    if is_api_executable_action(action):
        return None
    platform = normalize_backlog_key_part(action.get("platform"))
    kind = normalize_backlog_key_part(action.get("kind"))
    target = first_truthy(
        [
            action.get("target_url"),
            action.get("target_search_url"),
            action.get("target_uri"),
            action.get("target_author_handle"),
            action.get("target_author_display_name"),
            action.get("target_type"),
            action.get("target_search"),
            action.get("target_query"),
            action.get("title"),
        ]
    )
    target = normalize_backlog_key_part(target)
    if not platform or not kind or not target:
        return None
    return (platform, kind, target)


def backlog_keep_sort_key(action):
    return (
        action.get("date") or "",
        1 if action.get("status") == "approved" else 0,
        action.get("updated_at") or action.get("created_at") or "",
        action.get("action_id") or "",
    )


def skip_pending_action(action, timestamp, note):
    action["status"] = "skipped"
    action["updated_at"] = timestamp
    action["skipped_at"] = timestamp
    action.setdefault("notes", []).append({"at": timestamp, "text": note})


def latest_action_date(actions):
    dates = [str(action.get("date") or "") for action in actions if action.get("date")]
    return max(dates) if dates else None


def parse_action_day(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def normalize_backlog_key_part(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def list_follow_up_actions(path=DEFAULT_FOLLOW_UP_QUEUE_PATH, run_date=None, status=None):
    queue = load_follow_up_queue(path)
    actions = list(queue.get("actions", []))
    if run_date:
        actions = [action for action in actions if action.get("date") == run_date]
    if status:
        actions = [action for action in actions if action.get("status") == status]
    return actions


def automation_executable_actions(actions):
    return [action for action in actions if is_api_executable_action(action)]


def is_api_executable_action(action):
    if action.get("kind") != "reply_comment":
        return False
    platform = action.get("platform")
    if platform == "bluesky":
        return bool(action.get("target_url"))
    if platform == "threads":
        return bool(first_action_value(action, "target_thread_id", "target_media_id", "target_id"))
    if platform == "facebook":
        return bool(first_action_value(action, "target_object_id", "target_post_id", "target_id"))
    if platform == "instagram":
        return bool(first_action_value(action, "target_comment_id"))
    return False


def first_action_value(action, *keys):
    for key in keys:
        value = str(action.get(key) or "").strip()
        if value:
            return value
    return ""


def discover_follow_up_targets(
    post_refs,
    run_date,
    max_candidates_per_post=3,
    search_limit=20,
    max_age_days=21,
    now=None,
    exclude_handles=None,
    exclude_dids=None,
    search_posts_fn=None,
    exclude_threads_usernames=None,
):
    discovery = {}
    for post_index, ref in enumerate(post_refs, start=1):
        entry = ref["entry"]
        post = ref["post"]
        platform = entry.get("platform") or post.get("platform") or ""

        title = post.get("title") or entry.get("title") or ""
        topic = extract_topic(title)
        queries = build_discovery_queries(topic)
        group_id = reply_group_id(run_date, post_index)

        if platform == "bluesky":
            try:
                candidates = find_bluesky_reply_candidates(
                    queries,
                    max_candidates=max_candidates_per_post,
                    search_limit=search_limit,
                    max_age_days=max_age_days,
                    now=now,
                    exclude_handles=exclude_handles,
                    exclude_dids=exclude_dids,
                    search_posts_fn=search_posts_fn,
                )
            except BlueskyDiscoveryError as exc:
                discovery[group_id] = {"queries": queries, "candidates": [], "error": str(exc)}
                continue
        elif platform == "threads":
            try:
                candidates = find_threads_reply_candidates(
                    queries,
                    max_candidates=max_candidates_per_post,
                    search_limit=search_limit,
                    max_age_days=max_age_days,
                    now=now,
                    exclude_usernames=exclude_threads_usernames,
                )
            except ThreadsDiscoveryError as exc:
                discovery[group_id] = {
                    "queries": queries,
                    "candidates": manual_threads_search_candidates(queries, max_candidates=max_candidates_per_post),
                    "error": str(exc),
                }
                continue
        elif platform == "instagram":
            hashtags = build_instagram_hashtags(topic, post=post, queries=queries)
            try:
                candidates = find_instagram_reply_candidates(
                    hashtags,
                    max_candidates=max_candidates_per_post,
                    search_limit=search_limit,
                    max_age_days=min(max_age_days, 7),
                    now=now,
                )
            except InstagramDiscoveryError as exc:
                discovery[group_id] = {
                    "queries": hashtags,
                    "candidates": manual_instagram_hashtag_candidates(hashtags, max_candidates=max_candidates_per_post),
                    "error": str(exc),
                }
                continue
            queries = hashtags
        elif platform == "facebook":
            candidates = find_facebook_reply_candidates(
                queries,
                topic=topic,
                max_candidates=max_candidates_per_post,
            )
        else:
            continue

        discovery[group_id] = {"queries": queries, "candidates": candidates}
    return discovery


def approve_follow_up_action(action_id, approved_text=None, target_url=None, note=None, path=DEFAULT_FOLLOW_UP_QUEUE_PATH):
    return update_follow_up_action(
        action_id=action_id,
        status="approved",
        path=path,
        approved_text=approved_text,
        target_url=target_url,
        note=note,
    )


def mark_follow_up_action_sent(action_id, target_url=None, external_action_id=None, note=None, path=DEFAULT_FOLLOW_UP_QUEUE_PATH):
    return update_follow_up_action(
        action_id=action_id,
        status="sent",
        path=path,
        target_url=target_url,
        external_action_id=external_action_id,
        note=note,
    )


def skip_follow_up_action(action_id, note=None, path=DEFAULT_FOLLOW_UP_QUEUE_PATH):
    return update_follow_up_action(
        action_id=action_id,
        status="skipped",
        path=path,
        note=note,
    )


def update_follow_up_action(
    action_id,
    status,
    path=DEFAULT_FOLLOW_UP_QUEUE_PATH,
    approved_text=None,
    target_url=None,
    external_action_id=None,
    note=None,
):
    if status not in ACTION_STATUSES:
        raise ValueError(f"Unknown follow-up status: {status}")
    queue = load_follow_up_queue(path)
    action = find_follow_up_action(queue, action_id)
    now = datetime.now(timezone.utc).isoformat()
    action["status"] = status
    action["updated_at"] = now
    if status == "approved":
        action["approved_at"] = now
        action["approved_text"] = approved_text or action.get("approved_text") or action.get("draft_text", "")
    if status == "sent":
        action["sent_at"] = now
    if status == "skipped":
        action["skipped_at"] = now
    if target_url is not None:
        action["target_url"] = target_url
    if external_action_id is not None:
        action["external_action_id"] = external_action_id
    if note:
        action.setdefault("notes", []).append({"at": now, "text": note})
    save_follow_up_queue(queue, path)
    return action


def find_follow_up_action(queue, action_id):
    for action in queue.get("actions", []):
        if action.get("action_id") == action_id:
            return action
    raise ValueError(f"Unknown follow-up action: {action_id}")


def target_metadata_matches_url(action):
    handle = str(action.get("target_author_handle") or "").lower()
    target_url = str(action.get("target_url") or "")
    parsed = urlparse(target_url)
    parts = [part for part in parsed.path.split("/") if part]
    if (parsed.netloc or "").lower() == "bsky.app" and len(parts) >= 4 and parts[0] == "profile":
        if not handle:
            return False
        return parts[1].lower() == handle
    return True


def reply_action_id(run_date, post_index, draft_index):
    return f"FU-{run_date}-{post_index:02d}-R{draft_index}"


def reply_group_id(run_date, post_index):
    return f"FU-{run_date}-{post_index:02d}"


def outreach_action_id(run_date, outreach_index):
    return f"FU-{run_date}-O{outreach_index}"


def load_daily_plan(path):
    with Path(path).open() as handle:
        plan = json.load(handle)
    if not isinstance(plan, dict):
        raise ValueError("Daily plan must be a JSON object.")
    return plan


def load_posts_for_plan(plan, output_dir=Path("output")):
    output_path = Path(output_dir)
    run_date = plan["plan_date"]
    campaign = plan.get("campaign")
    refs = []
    for entry in plan.get("planned_posts", []):
        post, source_file = find_post_for_entry(entry, output_path, run_date, campaign)
        refs.append(
            {
                "entry": entry,
                "post": post or post_stub_from_entry(entry),
                "source_file": str(source_file) if source_file else "",
            }
        )
    return refs


def find_post_for_entry(entry, output_path, run_date, campaign=None):
    platform = entry.get("platform")
    shirt_id = entry.get("shirt_id")
    if not platform or not shirt_id:
        return None, None

    paths = sorted(output_path.glob(f"posts_{run_date}_{platform}*.json"), reverse=True)
    for path in paths:
        posts = load_json_list(path)
        for post in posts:
            if post.get("shirt_id") != shirt_id:
                continue
            if campaign and post.get("campaign") not in (campaign, None, ""):
                continue
            return post, path
    return None, None


def load_json_list(path):
    with Path(path).open() as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        return []
    return payload


def post_stub_from_entry(entry):
    return {
        "shirt_id": entry.get("shirt_id", ""),
        "title": entry.get("title", ""),
        "platform": entry.get("platform", ""),
        "content_goal": entry.get("content_goal", ""),
        "cta_goal": entry.get("cta_goal", ""),
        "caption": "",
    }


def load_publish_records(run_date, log_dir=Path("data"), platforms=None):
    selected_platforms = platforms or PUBLISH_LOG_FILENAMES.keys()
    records = []
    for platform in selected_platforms:
        filename = PUBLISH_LOG_FILENAMES.get(platform)
        if not filename:
            continue
        path = Path(log_dir) / filename
        if not path.exists():
            continue
        with path.open() as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                if payload.get("status") != "published":
                    continue
                if str(payload.get("logged_at", ""))[:10] != run_date:
                    continue
                record = dict(payload)
                record["platform"] = platform
                records.append(record)
    return records


def find_publish_record(post, entry, publish_records):
    platform = entry.get("platform") or post.get("platform")
    shirt_id = entry.get("shirt_id") or post.get("shirt_id")
    title = entry.get("title") or post.get("title")
    for record in reversed(publish_records):
        if record.get("platform") != platform:
            continue
        if shirt_id and record.get("shirt_id") == shirt_id:
            return record
        if title and record.get("title") == title:
            return record
    return None


def external_id_for_record(record):
    if not record:
        return ""
    for key in EXTERNAL_ID_KEYS:
        value = record.get(key)
        if value:
            return str(value)
    return ""


def write_follow_up_brief(markdown, run_date, output_dir=Path("output")):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    destination = output_path / f"follow_up_{run_date}.md"
    destination.write_text(markdown)
    return destination


def build_discovery_queries(topic):
    return [
        f"Colorado {topic}",
        f"Denver {topic}",
        f"Colorado memes {topic}",
        f"Colorado {topic} overrated",
        f"Denver weekend plans {topic}",
    ]


def build_reply_drafts(topic, content_goal, cta_goal, post):
    if content_goal == "direct_offer" or cta_goal == "buy":
        offer = post.get("active_offer") or "the current sale"
        return [
            f"The sale is temporary; opposition to {topic} can be a lifestyle.",
            f"{offer}. Use it before someone invites you to {topic} again.",
            f"Wear the position. Decline the unnecessary {topic} meeting.",
        ]
    if content_goal == "product_connected" or cta_goal == "vote":
        return [
            f"Current docket: {topic}. What Colorado sacred cow goes on trial next?",
            "Nominations are open: ski traffic, Red Rocks parking, Subaru culture, or something worse?",
            f"If {topic} is the gateway complaint, what is the final boss?",
        ]
    if cta_goal == "share":
        return [
            f"Send this to the friend who says {topic} is relaxing and then packs like they are crossing the Andes.",
            f"Colorado friendship test: who in the group chat is most likely to defend {topic}?",
            "The opposition may state its case, but please use indoor voices.",
        ]
    return [
        f"Colorado roll call: is {topic} actually fun, or did a group chat bully everyone into pretending?",
        f"We are not saying ban {topic}. We are saying stop assigning homework.",
        f"Defend {topic} in one sentence. No brochure language.",
    ]


def build_outreach_rows(series):
    return [
        (
            "Colorado meme page",
            "Search platform-native hashtags and posts for Colorado memes, Denver jokes, mountain traffic, and local complaint threads.",
            f"If you ever do a Colorado sacred cows bracket, the {series} series is basically pre-season material. Want us to send a few nominees?",
        ),
        (
            "Denver or Colorado newsletter",
            "Look for local culture newsletters, event roundups, and neighborhood pages that already share funny local observations.",
            f"We are collecting nominations for the next {series} target. If your readers have opinions, we would happily make them worse.",
        ),
        (
            "Micro-creator with local audience",
            "Search for creators posting Colorado lifestyle, hiking satire, brewery jokes, ski traffic, or transplant humor.",
            f"We are testing a local joke series called {series}. If your audience likes arguing about Colorado habits, we can set up a small giveaway or code.",
        ),
    ]


def extract_topic(title):
    text = re.sub(r"^coloradans\s+against\s+", "", str(title or ""), flags=re.IGNORECASE).strip()
    text = re.sub(r"\s+", " ", text)
    return text.lower() or "this"


def first_truthy(values):
    for value in values:
        if value:
            return value
    return None


def table_cell(value):
    return one_line(value).replace("|", "\\|")


def one_line(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()
