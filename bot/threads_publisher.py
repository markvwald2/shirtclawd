import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from bot.data_loader import load_inventory


THREADS_BASE_URL = "https://graph.threads.net/v1.0"
DEFAULT_PUBLISH_LOG_PATH = Path("data/threads_publish_log.jsonl")
DEFAULT_THREADS_USERNAME = "@3rdstringshirts"
MAX_POST_LENGTH = 500
MAX_CAROUSEL_ITEMS = 20


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
    media_items = resolve_post_media_items(post)
    image_urls = [item["image_url"] for item in media_items]
    resolved_image_url = image_urls[0] if image_urls else ""
    is_carousel = len(image_urls) > 1
    resolved_credentials = dict(credentials or {})
    resolved_username = username or resolved_credentials.get("username") or DEFAULT_THREADS_USERNAME
    resolved_user_id = resolved_credentials.get("user_id") or os.getenv("THREADS_USER_ID", "")
    result = {
        "mode": "dry_run" if dry_run else "publish",
        "shirt_id": post.get("shirt_id"),
        "shirt_ids": post.get("shirt_ids") or [],
        "title": post.get("title"),
        "text": text,
        "platform": "threads",
        "username": resolved_username,
        "user_id": resolved_user_id,
        "image_url": resolved_image_url,
        "image_urls": image_urls,
        "is_carousel": is_carousel,
    }

    if dry_run:
        log_publish_event(
            {
                "logged_at": utc_now_iso(),
                "status": "dry_run",
                "shirt_id": post.get("shirt_id"),
                "shirt_ids": post.get("shirt_ids") or [],
                "title": post.get("title"),
                "text": text,
                "username": resolved_username,
                "user_id": resolved_user_id,
                "image_url": resolved_image_url,
                "image_urls": image_urls,
                "is_carousel": is_carousel,
            },
            log_path,
        )
        return result

    resolved_credentials = credentials or load_credentials()
    if is_carousel:
        if len(media_items) > MAX_CAROUSEL_ITEMS:
            raise ThreadsPublisherError(
                f"Threads carousel publishing supports at most {MAX_CAROUSEL_ITEMS} items; got {len(media_items)}."
            )
        child_creation_ids = [
            create_carousel_item_container(
                user_id=resolved_credentials["user_id"],
                access_token=resolved_credentials["access_token"],
                image_url=item["image_url"],
                alt_text=item.get("alt_text"),
            )
            for item in media_items
        ]
        creation_id = create_carousel_container(
            user_id=resolved_credentials["user_id"],
            access_token=resolved_credentials["access_token"],
            text=text,
            child_creation_ids=child_creation_ids,
        )
    else:
        child_creation_ids = []
        creation_id = create_container(
            user_id=resolved_credentials["user_id"],
            access_token=resolved_credentials["access_token"],
            text=text,
            image_url=resolved_image_url,
            alt_text=media_items[0].get("alt_text") if media_items else post.get("alt_text"),
        )
    response = publish_container(
        user_id=resolved_credentials["user_id"],
        access_token=resolved_credentials["access_token"],
        creation_id=creation_id,
    )
    event = {
        "logged_at": utc_now_iso(),
        "status": "published_carousel" if is_carousel else "published",
        "shirt_id": post.get("shirt_id"),
        "shirt_ids": post.get("shirt_ids") or [],
        "title": post.get("title"),
        "text": text,
        "username": resolved_username,
        "user_id": resolved_credentials["user_id"],
        "image_url": resolved_image_url,
        "image_urls": image_urls,
        "is_carousel": is_carousel,
        "creation_id": creation_id,
        "child_creation_ids": child_creation_ids,
        "threads_media_id": response.get("id"),
    }
    log_publish_event(event, log_path)
    result.update(event)
    return result


def publish_reply(text, target_thread_id, dry_run=True, credentials=None, log_path=DEFAULT_PUBLISH_LOG_PATH, username=None):
    reply_text = trim_text(str(text or "").strip(), MAX_POST_LENGTH)
    resolved_credentials = dict(credentials or {})
    resolved_username = username or resolved_credentials.get("username") or DEFAULT_THREADS_USERNAME
    resolved_user_id = resolved_credentials.get("user_id") or os.getenv("THREADS_USER_ID", "")
    result = {
        "mode": "dry_run" if dry_run else "publish",
        "platform": "threads",
        "username": resolved_username,
        "user_id": resolved_user_id,
        "text": reply_text,
        "target_thread_id": str(target_thread_id or "").strip(),
        "action_type": "reply",
    }

    if not result["target_thread_id"]:
        raise ThreadsPublisherError("Missing Threads reply target_thread_id.")

    if dry_run:
        log_publish_event(
            {
                "logged_at": utc_now_iso(),
                "status": "dry_run_reply",
                "text": reply_text,
                "target_thread_id": result["target_thread_id"],
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
        text=reply_text,
        reply_to_id=result["target_thread_id"],
    )
    response = publish_container(
        user_id=resolved_credentials["user_id"],
        access_token=resolved_credentials["access_token"],
        creation_id=creation_id,
    )
    event = {
        "logged_at": utc_now_iso(),
        "status": "published_reply",
        "text": reply_text,
        "username": resolved_username,
        "user_id": resolved_credentials["user_id"],
        "target_thread_id": result["target_thread_id"],
        "creation_id": creation_id,
        "threads_media_id": response.get("id"),
    }
    log_publish_event(event, log_path)
    result.update(event)
    return result


def resolve_image_url(post):
    items = resolve_post_media_items(post)
    return items[0]["image_url"] if items else ""


def resolve_post_media_items(post):
    items = []
    carousel_items = post.get("carousel_items")
    if isinstance(carousel_items, list):
        for item in carousel_items:
            if isinstance(item, dict):
                items.append(
                    {
                        "image_url": item.get("image_url"),
                        "alt_text": item.get("alt_text") or item.get("title") or post.get("alt_text") or "",
                    }
                )
    image_urls = post.get("image_urls")
    if isinstance(image_urls, list):
        items.extend({"image_url": image_url, "alt_text": post.get("alt_text") or ""} for image_url in image_urls)
    image_url = str(post.get("image_url") or "").strip()
    if image_url:
        items.append({"image_url": image_url, "alt_text": post.get("alt_text") or ""})

    resolved = dedupe_media_items(items)
    if resolved:
        return resolved

    recovered = recover_image_url_from_inventory(post)
    if recovered:
        return [{"image_url": recovered, "alt_text": post.get("alt_text") or ""}]
    return []


def dedupe_media_items(items):
    resolved = []
    seen = set()
    for item in items:
        image_url = str(item.get("image_url") or "").strip()
        if not image_url or image_url in seen:
            continue
        seen.add(image_url)
        resolved.append(
            {
                "image_url": image_url,
                "alt_text": str(item.get("alt_text") or "").strip(),
            }
        )
    return resolved


def recover_image_url_from_inventory(post):
    lookup_key = str(post.get("shirt_id") or "").strip()
    lookup_url = str(post.get("url") or "").strip()
    if not lookup_key and not lookup_url:
        return ""

    try:
        inventory = load_inventory()
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        return ""

    for shirt in inventory:
        shirt_id = str(shirt.get("shirt_id") or "").strip()
        product_url = str(shirt.get("url") or "").strip()
        candidate = str(shirt.get("image_url") or "").strip()
        if not candidate:
            continue
        if lookup_key and shirt_id == lookup_key:
            return candidate
        if lookup_url and product_url == lookup_url:
            return candidate

    return ""


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


def create_container(user_id, access_token, text, image_url=None, alt_text=None, reply_to_id=None):
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
    if reply_to_id:
        payload["reply_to_id"] = reply_to_id

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


def create_carousel_item_container(user_id, access_token, image_url, alt_text=None):
    payload = {
        "media_type": "IMAGE",
        "image_url": image_url,
        "is_carousel_item": "true",
    }
    if alt_text:
        payload["alt_text"] = alt_text

    response = api_request(
        f"{THREADS_BASE_URL}/{user_id}/threads",
        payload=payload,
        method="POST",
        access_token=access_token,
    )
    creation_id = response.get("id")
    if not creation_id:
        raise ThreadsPublisherError(f"Threads carousel item response missing id: {response}")
    return creation_id


def create_carousel_container(user_id, access_token, text, child_creation_ids):
    children = [str(child_id).strip() for child_id in child_creation_ids if str(child_id).strip()]
    if len(children) < 2:
        raise ThreadsPublisherError("Threads carousel publishing requires at least two child media containers.")

    response = api_request(
        f"{THREADS_BASE_URL}/{user_id}/threads",
        payload={
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "text": text,
        },
        method="POST",
        access_token=access_token,
    )
    creation_id = response.get("id")
    if not creation_id:
        raise ThreadsPublisherError(f"Threads carousel container response missing id: {response}")
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
