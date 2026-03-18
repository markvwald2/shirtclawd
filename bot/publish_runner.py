import json
from pathlib import Path

from bot.approval_queue import load_approval_queue
from bot.x_publisher import (
    DEFAULT_PUBLISH_LOG_PATH,
    DEFAULT_X_HANDLE,
    XPublisherError,
    load_posts,
    publish_post,
    select_post,
)


def load_publish_log(path=DEFAULT_PUBLISH_LOG_PATH):
    log_path = Path(path)
    if not log_path.exists():
        return []

    events = []
    with log_path.open() as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                events.append(payload)
    return events


def build_published_keys(events):
    published = set()
    for event in events:
        if event.get("status") != "published":
            continue
        key = (
            str(event.get("shirt_id") or ""),
            str(event.get("handle") or DEFAULT_X_HANDLE),
        )
        published.add(key)
    return published


def publish_approved_x_posts(
    approval_queue_path=None,
    publish_log_path=DEFAULT_PUBLISH_LOG_PATH,
    handle=DEFAULT_X_HANDLE,
    dry_run=False,
):
    queue = load_approval_queue(approval_queue_path) if approval_queue_path else load_approval_queue()
    published_keys = build_published_keys(load_publish_log(publish_log_path))
    results = []

    for item in queue.get("approved_posts", []):
        if item.get("platform") != "x":
            continue
        item_handle = item.get("handle") or handle
        if item_handle != handle:
            continue

        publish_key = (str(item.get("shirt_id") or ""), str(item_handle))
        if publish_key in published_keys:
            continue

        source_file = item.get("source_file")
        if not source_file:
            continue

        posts = load_posts(source_file)
        post = select_post(posts, shirt_id=item.get("shirt_id"))
        results.append(
            publish_post(
                post,
                dry_run=dry_run,
                log_path=publish_log_path,
                handle=item_handle,
            )
        )
        if not dry_run:
            published_keys.add(publish_key)

    return results
