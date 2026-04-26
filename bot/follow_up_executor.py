import json
from datetime import datetime, timezone
from pathlib import Path

from bot.bluesky_publisher import BlueskyPublisherError, publish_reply as publish_bluesky_reply
from bot.follow_up import (
    DEFAULT_FOLLOW_UP_QUEUE_PATH,
    list_follow_up_actions,
    mark_follow_up_action_sent,
)


DEFAULT_FOLLOW_UP_EXECUTION_LOG_PATH = Path("data/follow_up_execution_log.jsonl")


def execute_approved_actions(
    queue_path=DEFAULT_FOLLOW_UP_QUEUE_PATH,
    dry_run=True,
    platform=None,
    action_id=None,
    limit=None,
    execution_log_path=DEFAULT_FOLLOW_UP_EXECUTION_LOG_PATH,
):
    actions = list_follow_up_actions(queue_path, status="approved")
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

    if action.get("platform") != "bluesky":
        return log_execution_result(
            action,
            {
                "status": "unsupported",
                "reason": f"Unsupported follow-up platform: {action.get('platform')}",
                "mode": "dry_run" if dry_run else "publish",
            },
            execution_log_path,
        )

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

    text = action.get("approved_text") or action.get("draft_text") or ""
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

    result = {
        "status": "dry_run" if dry_run else "sent",
        "mode": "dry_run" if dry_run else "publish",
        "target_url": target,
        "external_action_id": publish_result.get("uri", ""),
        "platform_result": publish_result,
    }
    if not dry_run:
        mark_follow_up_action_sent(
            action["action_id"],
            target_url=target,
            external_action_id=publish_result.get("uri", ""),
            path=queue_path,
        )
    return log_execution_result(action, result, execution_log_path)


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
