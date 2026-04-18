import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


THREADS_BASE_URL = "https://graph.threads.net/v1.0"
DEFAULT_PUBLISH_LOG_PATH = Path("data/threads_publish_log.jsonl")
DEFAULT_THREADS_USERNAME = "@3rdstringshirts"
MAX_POST_LENGTH = 500


class ThreadsPublisherError(RuntimeError):
    pass


def load_credentials(env=None):
    source = env or os.environ
    credentials = {
        "access_token": source.get("THREADS_ACCESS_TOKEN"),
        "user_id": source.get("THREADS_USER_ID"),
    }
    missing = [name for name, value in credentials.items() if not value]
    if missing:
        raise ThreadsPublisherError(f"Missing Threads credentials: {', '.join(missing)}")
    return credentials


def load_posts(path):
    with Path(path).open() as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ThreadsPublisherError("Post file must contain a JSON array.")
    return payload


def select_post(posts, index=None, shirt_id=None):
    if shirt_id:
        for post in posts:
            if post.get("shirt_id") == shirt_id:
                return post
        raise ThreadsPublisherError(f"No post found for shirt_id={shirt_id}")

    resolved_index = 0 if index is None else index
    if resolved_index < 0 or resolved_index >= len(posts):
        raise ThreadsPublisherError(f"Post index {resolved_index} is out of range for {len(posts)} posts.")
    return posts[resolved_index]


def publish_post(post, dry_run=True, credentials=None, log_path=DEFAULT_PUBLISH_LOG_PATH, username=None):
    text = build_threads_status(post)
    resolved_credentials = dict(credentials or {})
    resolved_username = username or resolved_credentials.get("username") or DEFAULT_THREADS_USERNAME
    resolved_user_id = resolved_credentials.get("user_id") or os.getenv("THREADS_USER_ID", "")
    result = {
        "mode": "dry_run" if dry_run else "publish",
        "shirt_id": post.get("shirt_id"),
        "title": post.get("title"),
        "text": text,
        "platform": "threads",
        "username": resolved_username,
        "user_id": resolved_user_id,
    }

    if dry_run:
        log_publish_event(
            {
                "logged_at": utc_now_iso(),
                "status": "dry_run",
                "shirt_id": post.get("shirt_id"),
                "title": post.get("title"),
                "text": text,
                "username": resolved_username,
                "user_id": resolved_user_id,
            },
            log_path,
        )
        return result

    resolved_credentials = credentials or load_credentials()
    creation_id = create_container(
        user_id=resolved_credentials["user_id"],
        access_token=resolved_credentials["access_token"],
        text=text,
        image_url=post.get("image_url"),
        alt_text=post.get("alt_text"),
    )
    response = publish_container(
        user_id=resolved_credentials["user_id"],
        access_token=resolved_credentials["access_token"],
        creation_id=creation_id,
    )
    event = {
        "logged_at": utc_now_iso(),
        "status": "published",
        "shirt_id": post.get("shirt_id"),
        "title": post.get("title"),
        "text": text,
        "username": resolved_username,
        "user_id": resolved_credentials["user_id"],
        "creation_id": creation_id,
        "threads_media_id": response.get("id"),
    }
    log_publish_event(event, log_path)
    result.update(event)
    return result


def build_threads_status(post, max_length=MAX_POST_LENGTH):
    caption = str(post.get("caption") or "").strip()
    if len(caption) <= max_length:
        return caption

    headline = (post.get("headline") or post.get("title") or "").strip()
    url = (post.get("url") or "").strip()
    hashtags = " ".join(post.get("hashtags") or [])
    compact = " ".join(part for part in [headline, url, hashtags] if part).strip()
    if len(compact) <= max_length:
        return compact

    reserve = len(url) + len(hashtags) + 2 if url or hashtags else 0
    available = max_length - reserve
    trimmed_headline = trim_text(headline, max(available, 0))
    final_text = " ".join(part for part in [trimmed_headline, url, hashtags] if part).strip()
    if len(final_text) <= max_length:
        return final_text

    return trim_text(caption, max_length)


def trim_text(text, limit):
    if len(text) <= limit:
        return text
    if limit <= 1:
        return text[:limit]
    return text[: limit - 1].rstrip() + "…"


def create_container(user_id, access_token, text, image_url=None, alt_text=None):
    payload = {"text": text}
    if image_url:
        payload.update(
            {
                "media_type": "IMAGE",
                "image_url": image_url,
            }
        )
        if alt_text:
            payload["alt_text"] = alt_text
    else:
        payload["media_type"] = "TEXT"

    response = api_request(
        f"{THREADS_BASE_URL}/{user_id}/threads",
        payload=payload,
        method="POST",
        access_token=access_token,
    )
    creation_id = response.get("id")
    if not creation_id:
        raise ThreadsPublisherError(f"Threads create container response missing id: {response}")
    return creation_id


def publish_container(user_id, access_token, creation_id):
    response = api_request(
        f"{THREADS_BASE_URL}/{user_id}/threads_publish",
        payload={"creation_id": creation_id},
        method="POST",
        access_token=access_token,
    )
    if not response.get("id"):
        raise ThreadsPublisherError(f"Unexpected Threads publish response: {response}")
    return response


def api_request(url, payload, method="POST", access_token=None):
    headers = {}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    if method == "GET":
        encoded = urlencode(payload)
        request = Request(f"{url}?{encoded}", headers=headers, method="GET")
    else:
        encoded = urlencode(payload)
        request = Request(
            url,
            data=encoded.encode("utf-8"),
            headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
            method=method,
        )

    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise ThreadsPublisherError(f"Threads API request failed: {exc.code} {error_body}") from exc
    except URLError as exc:
        raise ThreadsPublisherError(f"Threads API request failed: {exc}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ThreadsPublisherError(f"Threads API returned invalid JSON: {exc}") from exc


def log_publish_event(event, path=DEFAULT_PUBLISH_LOG_PATH):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a") as handle:
        handle.write(json.dumps(event))
        handle.write("\n")


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()
