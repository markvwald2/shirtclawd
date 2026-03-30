import json
import os
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


GRAPH_BASE_URL = "https://graph.instagram.com/v24.0"
DEFAULT_PUBLISH_LOG_PATH = Path("data/instagram_publish_log.jsonl")
DEFAULT_INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "replace_me")
MAX_CAPTION_LENGTH = 2200
PUBLISH_LIMIT_ERROR_SUBCODE = 2207042


class InstagramPublisherError(RuntimeError):
    pass


def load_credentials(env=None):
    source = env or os.environ
    credentials = {
        "access_token": source.get("INSTAGRAM_ACCESS_TOKEN"),
        "account_id": source.get("INSTAGRAM_BUSINESS_ACCOUNT_ID"),
    }
    missing = [name for name, value in credentials.items() if not value]
    if missing:
        raise InstagramPublisherError(f"Missing Instagram credentials: {', '.join(missing)}")
    return credentials


def load_posts(path):
    with Path(path).open() as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise InstagramPublisherError("Post file must contain a JSON array.")
    return payload


def select_post(posts, index=None, shirt_id=None):
    if shirt_id:
        for post in posts:
            if post.get("shirt_id") == shirt_id:
                return post
        raise InstagramPublisherError(f"No post found for shirt_id={shirt_id}")

    resolved_index = 0 if index is None else index
    if resolved_index < 0 or resolved_index >= len(posts):
        raise InstagramPublisherError(f"Post index {resolved_index} is out of range for {len(posts)} posts.")
    return posts[resolved_index]


def publish_post(post, dry_run=True, credentials=None, log_path=DEFAULT_PUBLISH_LOG_PATH, account_id=None):
    caption = build_instagram_caption(post)
    resolved_account_id = account_id or (credentials or {}).get("account_id") or DEFAULT_INSTAGRAM_ACCOUNT_ID
    result = {
        "mode": "dry_run" if dry_run else "publish",
        "shirt_id": post.get("shirt_id"),
        "title": post.get("title"),
        "caption": caption,
        "image_url": post.get("image_url"),
        "platform": "instagram",
        "account_id": resolved_account_id,
    }

    if dry_run:
        log_publish_event(
            {
                "logged_at": utc_now_iso(),
                "status": "dry_run",
                "shirt_id": post.get("shirt_id"),
                "title": post.get("title"),
                "caption": caption,
                "account_id": resolved_account_id,
            },
            log_path,
        )
        return result

    if not post.get("image_url"):
        raise InstagramPublisherError("Instagram publishing requires image_url for feed posts.")

    resolved_credentials = dict(credentials or load_credentials())
    if account_id:
        resolved_credentials["account_id"] = account_id
    limit_state = get_content_publishing_limit(credentials=resolved_credentials, account_id=resolved_credentials["account_id"])
    if limit_state.get("quota_total") is not None and limit_state.get("quota_usage", 0) >= limit_state["quota_total"]:
        raise InstagramPublisherError(
            f"Instagram content publishing limit reached: "
            f"{limit_state['quota_usage']}/{limit_state['quota_total']} used."
        )
    creation_id = create_media_container(
        account_id=resolved_credentials["account_id"],
        access_token=resolved_credentials["access_token"],
        image_url=post["image_url"],
        caption=caption,
    )
    wait_for_container(
        creation_id=creation_id,
        access_token=resolved_credentials["access_token"],
    )
    response = publish_media_container(
        account_id=resolved_credentials["account_id"],
        access_token=resolved_credentials["access_token"],
        creation_id=creation_id,
    )
    event = {
        "logged_at": utc_now_iso(),
        "status": "published",
        "shirt_id": post.get("shirt_id"),
        "title": post.get("title"),
        "caption": caption,
        "account_id": resolved_account_id,
        "creation_id": creation_id,
        "instagram_media_id": response.get("id"),
    }
    log_publish_event(event, log_path)
    result.update(event)
    return result


def build_instagram_caption(post, max_length=MAX_CAPTION_LENGTH):
    caption = strip_urls(post.get("caption") or "").strip()
    if len(caption) <= max_length:
        return caption

    headline = (post.get("headline") or post.get("title") or "").strip()
    hashtags = " ".join(post.get("hashtags") or [])
    compact = "\n\n".join(part for part in [headline, hashtags] if part)
    if len(compact) <= max_length:
        return compact

    return trim_text(caption, max_length)


def trim_text(text, limit):
    if len(text) <= limit:
        return text
    if limit <= 1:
        return text[:limit]
    return text[: limit - 1].rstrip() + "…"


def strip_urls(text):
    stripped = re.sub(r"https?://\S+", "", str(text or ""), flags=re.IGNORECASE)
    stripped = re.sub(r"[ \t]+", " ", stripped)
    stripped = re.sub(r" *\n *", "\n", stripped)
    stripped = re.sub(r"\n{3,}", "\n\n", stripped)
    return stripped.strip()


def create_media_container(account_id, access_token, image_url, caption):
    payload = {
        "image_url": image_url,
        "caption": caption,
    }
    response = api_request(
        f"{GRAPH_BASE_URL}/{account_id}/media",
        payload=payload,
        method="POST",
        access_token=access_token,
    )
    creation_id = response.get("id")
    if not creation_id:
        raise InstagramPublisherError(f"Instagram media creation response missing id: {response}")
    return creation_id


def wait_for_container(creation_id, access_token, max_attempts=10, delay_seconds=2):
    last_status = None
    for _ in range(max_attempts):
        response = api_request(
            f"{GRAPH_BASE_URL}/{creation_id}",
            payload={
                "fields": "status_code,status",
            },
            method="GET",
            access_token=access_token,
        )
        last_status = (response.get("status_code") or response.get("status") or "").upper()
        if last_status in {"FINISHED", "PUBLISHED"}:
            return response
        if last_status in {"ERROR", "EXPIRED"}:
            raise InstagramPublisherError(f"Instagram media container failed with status {last_status}: {response}")
        time.sleep(delay_seconds)
    raise InstagramPublisherError(f"Instagram media container was not ready after polling: {last_status or 'UNKNOWN'}")


def publish_media_container(account_id, access_token, creation_id):
    response = api_request(
        f"{GRAPH_BASE_URL}/{account_id}/media_publish",
        payload={
            "creation_id": creation_id,
        },
        method="POST",
        access_token=access_token,
    )
    if not response.get("id"):
        raise InstagramPublisherError(f"Unexpected Instagram publish response: {response}")
    return response


def get_content_publishing_limit(credentials=None, account_id=None):
    resolved_credentials = dict(credentials or load_credentials())
    resolved_account_id = account_id or resolved_credentials.get("account_id") or DEFAULT_INSTAGRAM_ACCOUNT_ID
    if not resolved_account_id:
        raise InstagramPublisherError("Missing Instagram account_id for content publishing limit check.")

    response = api_request(
        f"{GRAPH_BASE_URL}/{resolved_account_id}/content_publishing_limit",
        payload={"fields": "config,quota_usage"},
        method="GET",
        access_token=resolved_credentials["access_token"],
    )
    return normalize_limit_response(response)


def normalize_limit_response(response):
    payload = response
    if isinstance(response.get("data"), list) and response["data"]:
        payload = response["data"][0]

    config = payload.get("config") or {}
    quota_total = first_int(
        config.get("quota_total"),
        config.get("total"),
        payload.get("quota_total"),
        payload.get("total"),
    )
    quota_usage = first_int(
        payload.get("quota_usage"),
        payload.get("usage"),
    )
    return {
        "quota_total": quota_total,
        "quota_usage": quota_usage or 0,
        "raw": response,
    }


def first_int(*values):
    for value in values:
        try:
            if value is None or value == "":
                continue
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def api_request(url, payload, method="POST", access_token=None):
    headers = {}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    if method == "GET":
        encoded = urlencode(payload)
        request = Request(f"{url}?{encoded}", headers=headers, method="GET")
    else:
        request = Request(
            url,
            data=urlencode(payload).encode("utf-8"),
            headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
            method=method,
        )
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise InstagramPublisherError(f"Instagram API request failed: {exc.code} {error_body}") from exc
    except URLError as exc:
        raise InstagramPublisherError(f"Instagram API request failed: {exc}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InstagramPublisherError(f"Instagram API returned invalid JSON: {exc}") from exc


def log_publish_event(event, path=DEFAULT_PUBLISH_LOG_PATH):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a") as handle:
        handle.write(json.dumps(event) + "\n")


def utc_now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
