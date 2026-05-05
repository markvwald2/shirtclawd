import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


GRAPH_BASE_URL = "https://graph.facebook.com/v24.0"
DEFAULT_PUBLISH_LOG_PATH = Path("data/facebook_publish_log.jsonl")
DEFAULT_FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "replace_me")
CANONICAL_PRODUCT_BASE_URL = "https://www.thirdstringshirts.com/shirt"


class FacebookPublisherError(RuntimeError):
    pass


def load_credentials(env=None):
    source = env or os.environ
    credentials = {
        "access_token": source.get("FACEBOOK_PAGE_ACCESS_TOKEN"),
        "page_id": source.get("FACEBOOK_PAGE_ID"),
    }
    missing = [name for name, value in credentials.items() if not value]
    if missing:
        raise FacebookPublisherError(f"Missing Facebook credentials: {', '.join(missing)}")
    return credentials


def load_posts(path):
    with Path(path).open() as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise FacebookPublisherError("Post file must contain a JSON array.")
    return payload


def select_post(posts, index=None, shirt_id=None):
    if shirt_id:
        for post in posts:
            if post.get("shirt_id") == shirt_id:
                return post
        raise FacebookPublisherError(f"No post found for shirt_id={shirt_id}")

    resolved_index = 0 if index is None else index
    if resolved_index < 0 or resolved_index >= len(posts):
        raise FacebookPublisherError(f"Post index {resolved_index} is out of range for {len(posts)} posts.")
    return posts[resolved_index]


def publish_post(post, dry_run=True, credentials=None, log_path=DEFAULT_PUBLISH_LOG_PATH, page_id=None):
    message = build_facebook_message(post)
    link = build_facebook_link(post)
    image_urls = resolve_post_image_urls(post)
    is_multi_image = len(image_urls) > 1
    resolved_page_id = page_id or (credentials or {}).get("page_id") or DEFAULT_FACEBOOK_PAGE_ID
    result = {
        "mode": "dry_run" if dry_run else "publish",
        "shirt_id": post.get("shirt_id"),
        "shirt_ids": post.get("shirt_ids") or [],
        "title": post.get("title"),
        "message": message,
        "link": "" if is_multi_image else link,
        "image_url": image_urls[0] if image_urls else post.get("image_url"),
        "image_urls": image_urls,
        "is_multi_image": is_multi_image,
        "platform": "facebook",
        "page_id": resolved_page_id,
    }

    if dry_run:
        event = {
            "logged_at": utc_now_iso(),
            "status": "dry_run",
            "shirt_id": post.get("shirt_id"),
            "shirt_ids": post.get("shirt_ids") or [],
            "title": post.get("title"),
            "message": message,
            "link": "" if is_multi_image else link,
            "image_urls": image_urls,
            "is_multi_image": is_multi_image,
            "page_id": resolved_page_id,
        }
        log_publish_event(event, log_path)
        result.update(event)
        return result

    resolved_credentials = dict(credentials or load_credentials())
    if page_id:
        resolved_credentials["page_id"] = page_id

    if is_multi_image:
        photo_ids = [
            create_unpublished_photo(
                page_id=resolved_credentials["page_id"],
                access_token=resolved_credentials["access_token"],
                image_url=image_url,
            )
            for image_url in image_urls
        ]
        response = create_multi_photo_post(
            page_id=resolved_credentials["page_id"],
            access_token=resolved_credentials["access_token"],
            message=message,
            photo_ids=photo_ids,
        )
    else:
        photo_ids = []
        response = create_page_post(
            page_id=resolved_credentials["page_id"],
            access_token=resolved_credentials["access_token"],
            message=message,
            link=link,
        )
    event = {
        "logged_at": utc_now_iso(),
        "status": "published_multi_photo" if is_multi_image else "published",
        "shirt_id": post.get("shirt_id"),
        "shirt_ids": post.get("shirt_ids") or [],
        "title": post.get("title"),
        "message": message,
        "link": "" if is_multi_image else link,
        "image_urls": image_urls,
        "is_multi_image": is_multi_image,
        "facebook_photo_ids": photo_ids,
        "page_id": resolved_page_id,
        "facebook_post_id": response.get("post_id") or response.get("id"),
    }
    log_publish_event(event, log_path)
    result.update(event)
    return result


def publish_comment(text, target_object_id, dry_run=True, credentials=None, log_path=DEFAULT_PUBLISH_LOG_PATH, page_id=None):
    message = str(text or "").strip()
    target = str(target_object_id or "").strip()
    resolved_page_id = page_id or (credentials or {}).get("page_id") or DEFAULT_FACEBOOK_PAGE_ID
    result = {
        "mode": "dry_run" if dry_run else "publish",
        "platform": "facebook",
        "page_id": resolved_page_id,
        "message": message,
        "target_object_id": target,
        "action_type": "comment",
    }

    if not target:
        raise FacebookPublisherError("Missing Facebook comment target_object_id.")

    if dry_run:
        log_publish_event(
            {
                "logged_at": utc_now_iso(),
                "status": "dry_run_comment",
                "message": message,
                "page_id": resolved_page_id,
                "target_object_id": target,
            },
            log_path,
        )
        return result

    resolved_credentials = dict(credentials or load_credentials())
    if page_id:
        resolved_credentials["page_id"] = page_id

    response = create_object_comment(
        object_id=target,
        access_token=resolved_credentials["access_token"],
        message=message,
    )
    event = {
        "logged_at": utc_now_iso(),
        "status": "published_comment",
        "message": message,
        "page_id": resolved_page_id,
        "target_object_id": target,
        "facebook_comment_id": response.get("id"),
    }
    log_publish_event(event, log_path)
    result.update(event)
    return result


def build_facebook_message(post):
    message = str(post.get("caption") or "").strip()
    if message:
        return message

    headline = str(post.get("headline") or post.get("title") or "").strip()
    url = str(post.get("url") or "").strip()
    hashtags = " ".join(post.get("hashtags") or [])
    return "\n\n".join(part for part in [headline, url, hashtags] if part).strip()


def build_facebook_link(post):
    url = str(post.get("url") or "").strip()
    if "/shirt/" in url:
        return url

    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    should_rewrite = "thirdstringshirts.com" in hostname and parsed.path.endswith("/shop.html")
    if not should_rewrite:
        return url

    shirt_id = str(post.get("shirt_id") or "").strip()
    title = str(post.get("title") or "").strip()
    if shirt_id and title:
        slug = slugify_title(title)
        if slug:
            return f"{CANONICAL_PRODUCT_BASE_URL}/{slug}-{shirt_id}/index.html"

    return url


def resolve_post_image_urls(post):
    values = []
    carousel_items = post.get("carousel_items")
    if isinstance(carousel_items, list):
        values.extend(item.get("image_url") for item in carousel_items if isinstance(item, dict))
    image_urls = post.get("image_urls")
    if isinstance(image_urls, list):
        values.extend(image_urls)
    if post.get("image_url"):
        values.append(post.get("image_url"))

    resolved = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            resolved.append(text)
    return resolved


def slugify_title(title):
    normalized = re.sub(r"[^a-z0-9]+", "-", str(title or "").lower())
    return normalized.strip("-")


def create_page_post(page_id, access_token, message, link=""):
    payload = {"message": message}
    endpoint = f"{GRAPH_BASE_URL}/{page_id}/feed"
    if link:
        payload["link"] = link

    response = api_request(
        endpoint,
        payload=payload,
        method="POST",
        access_token=access_token,
    )
    if not response.get("id"):
        raise FacebookPublisherError(f"Unexpected Facebook publish response: {response}")
    return response


def create_unpublished_photo(page_id, access_token, image_url):
    response = api_request(
        f"{GRAPH_BASE_URL}/{page_id}/photos",
        payload={
            "url": image_url,
            "published": "false",
        },
        method="POST",
        access_token=access_token,
    )
    photo_id = response.get("id")
    if not photo_id:
        raise FacebookPublisherError(f"Unexpected Facebook photo upload response: {response}")
    return photo_id


def create_multi_photo_post(page_id, access_token, message, photo_ids):
    ids = [str(photo_id).strip() for photo_id in photo_ids if str(photo_id).strip()]
    if len(ids) < 2:
        raise FacebookPublisherError("Facebook multi-photo publishing requires at least two uploaded photo IDs.")

    payload = {"message": message}
    for index, photo_id in enumerate(ids):
        payload[f"attached_media[{index}]"] = json.dumps({"media_fbid": photo_id})

    response = api_request(
        f"{GRAPH_BASE_URL}/{page_id}/feed",
        payload=payload,
        method="POST",
        access_token=access_token,
    )
    if not response.get("id"):
        raise FacebookPublisherError(f"Unexpected Facebook multi-photo publish response: {response}")
    return response


def create_object_comment(object_id, access_token, message):
    response = api_request(
        f"{GRAPH_BASE_URL}/{object_id}/comments",
        payload={"message": message},
        method="POST",
        access_token=access_token,
    )
    if not response.get("id"):
        raise FacebookPublisherError(f"Unexpected Facebook comment response: {response}")
    return response


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
        raise FacebookPublisherError(f"Facebook API request failed: {exc.code} {error_body}") from exc
    except URLError as exc:
        raise FacebookPublisherError(f"Facebook API request failed: {exc}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FacebookPublisherError(f"Facebook API returned invalid JSON: {exc}") from exc


def log_publish_event(event, path=DEFAULT_PUBLISH_LOG_PATH):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a") as handle:
        handle.write(json.dumps(event))
        handle.write("\n")


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()
