import json
import re
from datetime import datetime, timezone
from pathlib import Path

from bot.bluesky_publisher import BlueskyPublisherError, publish_reply as publish_bluesky_reply
from bot.facebook_publisher import FacebookPublisherError, publish_comment as publish_facebook_comment
from bot.follow_up import (
    DEFAULT_FOLLOW_UP_QUEUE_PATH,
    list_follow_up_actions,
    mark_follow_up_action_sent,
)
from bot.instagram_publisher import InstagramPublisherError, publish_comment_reply as publish_instagram_comment_reply
from bot.threads_publisher import ThreadsPublisherError, publish_reply as publish_threads_reply


DEFAULT_FOLLOW_UP_EXECUTION_LOG_PATH = Path("data/follow_up_execution_log.jsonl")


def execute_approved_actions(
    queue_path=DEFAULT_FOLLOW_UP_QUEUE_PATH,
    dry_run=True,
    platform=None,
    action_id=None,
    limit=None,
    execution_log_path=DEFAULT_FOLLOW_UP_EXECUTION_LOG_PATH,
    run_date=None,
):
    actions = list_follow_up_actions(queue_path, status="approved")
    if run_date:
        actions = [action for action in actions if action.get("date") == run_date]
    if platform:
        actions = [action for action in actions if action.get("platform") == platform]
    if action_id:
        actions = [action for action in actions if action.get("action_id") == action_id]
    if limit is not None:
        actions = actions[: max(int(limit), 0)]

    results = []
    for action in actions:
        result = execute_action(
            action,
            dry_run=dry_run,
            queue_path=queue_path,
            execution_log_path=execution_log_path,
        )
        results.append(result)
    return results


def execute_action(action, dry_run=True, queue_path=DEFAULT_FOLLOW_UP_QUEUE_PATH, execution_log_path=DEFAULT_FOLLOW_UP_EXECUTION_LOG_PATH):
    if action.get("kind") == "outreach_dm":
        return manual_required(
            action,
            "Outreach DMs remain manual; automated cold DMs are not enabled.",
            dry_run=dry_run,
            execution_log_path=execution_log_path,
        )
    if action.get("kind") != "reply_comment":
        return log_execution_result(
            action,
            {
                "status": "unsupported",
                "reason": f"Unsupported action kind: {action.get('kind')}",
                "mode": "dry_run" if dry_run else "publish",
            },
            execution_log_path,
        )

    platform = action.get("platform")
    if platform == "bluesky":
        return execute_bluesky_reply(
            action,
            dry_run=dry_run,
            queue_path=queue_path,
            execution_log_path=execution_log_path,
        )
    if platform == "threads":
        return execute_threads_reply(
            action,
            dry_run=dry_run,
            queue_path=queue_path,
            execution_log_path=execution_log_path,
        )
    if platform == "facebook":
        return execute_facebook_comment(
            action,
            dry_run=dry_run,
            queue_path=queue_path,
            execution_log_path=execution_log_path,
        )
    if platform == "instagram":
        return execute_instagram_comment_reply(
            action,
            dry_run=dry_run,
            queue_path=queue_path,
            execution_log_path=execution_log_path,
        )

    return log_execution_result(
        action,
        {
            "status": "unsupported",
            "reason": f"Unsupported follow-up platform: {platform}",
            "mode": "dry_run" if dry_run else "publish",
        },
        execution_log_path,
    )


def execute_bluesky_reply(action, dry_run=True, queue_path=DEFAULT_FOLLOW_UP_QUEUE_PATH, execution_log_path=DEFAULT_FOLLOW_UP_EXECUTION_LOG_PATH):
    target = action.get("target_url")
    if not target:
        return log_execution_result(
            action,
            {
                "status": "missing_target",
                "reason": "Approved action needs target_url before execution.",
                "mode": "dry_run" if dry_run else "publish",
            },
            execution_log_path,
        )

    text = action_text(action)
    try:
        publish_result = publish_bluesky_reply(
            text=text,
            target=target,
            dry_run=dry_run,
        )
    except BlueskyPublisherError as exc:
        return log_execution_result(
            action,
            {
                "status": "error",
                "reason": str(exc),
                "mode": "dry_run" if dry_run else "publish",
            },
            execution_log_path,
        )

    return record_publish_result(
        action,
        publish_result,
        dry_run=dry_run,
        queue_path=queue_path,
        execution_log_path=execution_log_path,
        target_url=target,
    )


def execute_threads_reply(action, dry_run=True, queue_path=DEFAULT_FOLLOW_UP_QUEUE_PATH, execution_log_path=DEFAULT_FOLLOW_UP_EXECUTION_LOG_PATH):
    target = first_action_value(action, "target_thread_id", "target_media_id", "target_id")
    if not target:
        target_url = str(action.get("target_url") or "")
        if is_non_url_identifier(target_url):
            target = target_url
    if not target:
        return manual_required(
            action,
            "Threads replies need a specific Threads media/reply ID, not a search URL.",
            dry_run=dry_run,
            execution_log_path=execution_log_path,
        )

    text = action_text(action)
    try:
        publish_result = publish_threads_reply(
            text=text,
            target_thread_id=target,
            dry_run=dry_run,
        )
    except ThreadsPublisherError as exc:
        return log_execution_result(
            action,
            {
                "status": "error",
                "reason": str(exc),
                "mode": "dry_run" if dry_run else "publish",
            },
            execution_log_path,
        )

    return record_publish_result(
        action,
        publish_result,
        dry_run=dry_run,
        queue_path=queue_path,
        execution_log_path=execution_log_path,
        target_url=action.get("target_url"),
    )


def execute_facebook_comment(action, dry_run=True, queue_path=DEFAULT_FOLLOW_UP_QUEUE_PATH, execution_log_path=DEFAULT_FOLLOW_UP_EXECUTION_LOG_PATH):
    target = first_action_value(action, "target_object_id", "target_post_id", "target_id")
    if not target:
        target_url = str(action.get("target_url") or "")
        if is_facebook_object_id(target_url):
            target = target_url
    if not target:
        return manual_required(
            action,
            "Facebook comments need a specific Graph object ID for a post/photo/video.",
            dry_run=dry_run,
            execution_log_path=execution_log_path,
        )

    text = action_text(action)
    try:
        publish_result = publish_facebook_comment(
            text=text,
            target_object_id=target,
            dry_run=dry_run,
        )
    except FacebookPublisherError as exc:
        return log_execution_result(
            action,
            {
                "status": "error",
                "reason": str(exc),
                "mode": "dry_run" if dry_run else "publish",
            },
            execution_log_path,
        )

    return record_publish_result(
        action,
        publish_result,
        dry_run=dry_run,
        queue_path=queue_path,
        execution_log_path=execution_log_path,
        target_url=action.get("target_url") or target,
    )


def execute_instagram_comment_reply(action, dry_run=True, queue_path=DEFAULT_FOLLOW_UP_QUEUE_PATH, execution_log_path=DEFAULT_FOLLOW_UP_EXECUTION_LOG_PATH):
    target = first_action_value(action, "target_comment_id")
    if not target:
        return manual_required(
            action,
            "Instagram API execution only supports replies to owned-media comments by IG comment ID.",
            dry_run=dry_run,
            execution_log_path=execution_log_path,
        )

    text = action_text(action)
    try:
        publish_result = publish_instagram_comment_reply(
            text=text,
            target_comment_id=target,
            dry_run=dry_run,
        )
    except InstagramPublisherError as exc:
        return log_execution_result(
            action,
            {
                "status": "error",
                "reason": str(exc),
                "mode": "dry_run" if dry_run else "publish",
            },
            execution_log_path,
        )

    return record_publish_result(
        action,
        publish_result,
        dry_run=dry_run,
        queue_path=queue_path,
        execution_log_path=execution_log_path,
        target_url=action.get("target_url") or target,
    )


def record_publish_result(action, publish_result, dry_run=True, queue_path=DEFAULT_FOLLOW_UP_QUEUE_PATH, execution_log_path=DEFAULT_FOLLOW_UP_EXECUTION_LOG_PATH, target_url=None):
    external_action_id = external_id_from_result(publish_result)
    result = {
        "status": "dry_run" if dry_run else "sent",
        "mode": "dry_run" if dry_run else "publish",
        "target_url": target_url or "",
        "external_action_id": external_action_id,
        "platform_result": publish_result,
    }
    if not dry_run:
        mark_follow_up_action_sent(
            action["action_id"],
            target_url=target_url,
            external_action_id=external_action_id,
            path=queue_path,
        )
    return log_execution_result(action, result, execution_log_path)


def manual_required(action, reason, dry_run=True, execution_log_path=DEFAULT_FOLLOW_UP_EXECUTION_LOG_PATH):
    return log_execution_result(
        action,
        {
            "status": "manual_required",
            "reason": reason,
            "mode": "dry_run" if dry_run else "publish",
            "target_url": action.get("target_url", ""),
            "copy": action_text(action),
        },
        execution_log_path,
    )


def action_text(action):
    return action.get("approved_text") or action.get("draft_text") or ""


def first_action_value(action, *keys):
    for key in keys:
        value = str(action.get(key) or "").strip()
        if value:
            return value
    return ""


def external_id_from_result(result):
    for key in ("uri", "threads_media_id", "facebook_comment_id", "instagram_comment_id", "id", "message_id"):
        value = result.get(key)
        if value:
            return value
    return ""


def is_non_url_identifier(value):
    candidate = str(value or "").strip()
    return bool(candidate) and "://" not in candidate and "/" not in candidate


def is_facebook_object_id(value):
    return bool(re.fullmatch(r"\d+_\d+|\d+", str(value or "").strip()))


def log_execution_result(action, result, path=DEFAULT_FOLLOW_UP_EXECUTION_LOG_PATH):
    event = {
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "action_id": action.get("action_id"),
        "platform": action.get("platform"),
        "kind": action.get("kind"),
        **result,
    }
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a") as handle:
        handle.write(json.dumps(event))
        handle.write("\n")
    return event
