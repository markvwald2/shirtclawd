from bot.bluesky_discovery import bsky_post_url, parse_datetime
from bot.bluesky_publisher import (
    BLUESKY_BASE_URL,
    BlueskyPublisherError,
    create_session,
    get_json_request,
    load_credentials,
)


LIST_NOTIFICATIONS_URL = f"{BLUESKY_BASE_URL}/xrpc/app.bsky.notification.listNotifications"
ACTIONABLE_NOTIFICATION_REASONS = {"reply", "mention", "quote"}
DEFAULT_NOTIFICATION_LIMIT = 50


class BlueskyInboxError(RuntimeError):
    pass


def fetch_bluesky_inbox_items(
    since=None,
    limit=DEFAULT_NOTIFICATION_LIMIT,
    credentials=None,
    list_notifications_fn=None,
):
    notifications = (list_notifications_fn or list_notifications)(
        since=since,
        limit=limit,
        credentials=credentials,
    )
    since_at = parse_datetime(since) if since else None
    items = []
    for notification in notifications:
        item = inbox_item_from_notification(notification)
        if not item:
            continue
        indexed_at = parse_datetime(item.get("indexed_at"))
        if since_at and indexed_at and indexed_at <= since_at:
            continue
        items.append(item)
    return sorted(items, key=lambda item: item.get("indexed_at", ""))


def list_notifications(since=None, limit=DEFAULT_NOTIFICATION_LIMIT, credentials=None):
    try:
        session = create_session(credentials or load_credentials())
        payload = {
            "limit": max(1, min(int(limit or DEFAULT_NOTIFICATION_LIMIT), 100)),
        }
        response = get_json_request(
            LIST_NOTIFICATIONS_URL,
            payload,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {session['accessJwt']}",
            },
        )
    except BlueskyPublisherError as exc:
        raise BlueskyInboxError(str(exc)) from exc

    notifications = response.get("notifications")
    if not isinstance(notifications, list):
        raise BlueskyInboxError(f"Unexpected Bluesky notifications response: {response}")
    return notifications


def inbox_item_from_notification(notification):
    if not isinstance(notification, dict):
        return None
    reason = str(notification.get("reason") or "")
    if reason not in ACTIONABLE_NOTIFICATION_REASONS:
        return None

    author = notification.get("author") or {}
    record = notification.get("record") or {}
    handle = str(author.get("handle") or "")
    uri = str(notification.get("uri") or "")
    indexed_at = str(notification.get("indexedAt") or "")
    text = clean_notification_text(record.get("text") or "")
    if not handle or not uri or not indexed_at:
        return None

    return {
        "platform": "bluesky",
        "reason": reason,
        "uri": uri,
        "cid": str(notification.get("cid") or ""),
        "reason_subject": str(notification.get("reasonSubject") or ""),
        "author_handle": handle,
        "author_display_name": author.get("displayName") or handle,
        "author_did": author.get("did") or "",
        "text": text,
        "indexed_at": indexed_at,
        "url": bsky_post_url(handle, uri),
        "profile_url": f"https://bsky.app/profile/{handle}",
        "is_read": bool(notification.get("isRead")),
    }

def clean_notification_text(text):
    return " ".join(str(text or "").split())
