import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_APPROVAL_QUEUE_PATH = Path("data/x_approval_queue.json")
DEFAULT_BLUESKY_APPROVAL_QUEUE_PATH = Path("data/bluesky_approval_queue.json")


def load_approval_queue(path=DEFAULT_APPROVAL_QUEUE_PATH):
    queue_path = Path(path)
    if not queue_path.exists():
        return {"approved_posts": []}

    with queue_path.open() as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict) or "approved_posts" not in payload:
        return {"approved_posts": []}

    return payload


def save_approval_queue(queue, path=DEFAULT_APPROVAL_QUEUE_PATH):
    queue_path = Path(path)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    with queue_path.open("w") as handle:
        json.dump(queue, handle, indent=2)
        handle.write("\n")


def approve_post(post, source_file, handle, path=DEFAULT_APPROVAL_QUEUE_PATH, platform="x"):
    queue = load_approval_queue(path)
    approved_posts = [
        item
        for item in queue["approved_posts"]
        if not (
            item.get("shirt_id") == post.get("shirt_id")
            and item.get("source_file") == str(source_file)
            and item.get("platform", "x") == platform
        )
    ]
    approved_posts.append(
        {
            "shirt_id": post.get("shirt_id"),
            "title": post.get("title"),
            "source_file": str(source_file),
            "platform": platform,
            "handle": handle,
            "approved_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    queue["approved_posts"] = sorted(
        approved_posts,
        key=lambda item: item.get("approved_at", ""),
        reverse=True,
    )[:200]
    save_approval_queue(queue, path)
    return queue


def is_post_approved(post, source_file, handle=None, path=DEFAULT_APPROVAL_QUEUE_PATH, platform="x"):
    queue = load_approval_queue(path)
    for item in queue["approved_posts"]:
        if item.get("shirt_id") != post.get("shirt_id"):
            continue
        if item.get("source_file") != str(source_file):
            continue
        if item.get("platform", "x") != platform:
            continue
        if handle and item.get("handle") != handle:
            continue
        return True
    return False
