import json
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BLUESKY_BASE_URL = "https://bsky.social"
CREATE_SESSION_URL = f"{BLUESKY_BASE_URL}/xrpc/com.atproto.server.createSession"
CREATE_RECORD_URL = f"{BLUESKY_BASE_URL}/xrpc/com.atproto.repo.createRecord"
UPLOAD_BLOB_URL = f"{BLUESKY_BASE_URL}/xrpc/com.atproto.repo.uploadBlob"
DEFAULT_PUBLISH_LOG_PATH = Path("data/bluesky_publish_log.jsonl")
DEFAULT_BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE", "replace-me.bsky.social")
MAX_POST_LENGTH = 300
MAX_BLOB_BYTES = 950_000
BLUESKY_RESIZE_WIDTHS = (1600, 1200, 900, 700, 500)


class BlueskyPublisherError(RuntimeError):
    pass


def load_credentials(env=None):
    source = env or os.environ
    credentials = {
        "handle": source.get("BLUESKY_HANDLE"),
        "app_password": source.get("BLUESKY_APP_PASSWORD"),
    }
    missing = [name for name, value in credentials.items() if not value]
    if missing:
        raise BlueskyPublisherError(f"Missing Bluesky credentials: {', '.join(missing)}")
    return credentials


def load_posts(path):
    with Path(path).open() as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise BlueskyPublisherError("Post file must contain a JSON array.")
    return payload


def select_post(posts, index=None, shirt_id=None):
    if shirt_id:
        for post in posts:
            if post.get("shirt_id") == shirt_id:
                return post
        raise BlueskyPublisherError(f"No post found for shirt_id={shirt_id}")

    resolved_index = 0 if index is None else index
    if resolved_index < 0 or resolved_index >= len(posts):
        raise BlueskyPublisherError(f"Post index {resolved_index} is out of range for {len(posts)} posts.")
    return posts[resolved_index]


def publish_post(post, dry_run=True, credentials=None, log_path=DEFAULT_PUBLISH_LOG_PATH, handle=None):
    text = build_bluesky_status(post)
    resolved_handle = handle or (credentials or {}).get("handle") or DEFAULT_BLUESKY_HANDLE
    result = {
        "mode": "dry_run" if dry_run else "publish",
        "shirt_id": post.get("shirt_id"),
        "title": post.get("title"),
        "text": text,
        "image_url": post.get("image_url"),
        "platform": "bluesky",
        "handle": resolved_handle,
    }

    if dry_run:
        log_publish_event(
            {
                "logged_at": utc_now_iso(),
                "status": "dry_run",
                "shirt_id": post.get("shirt_id"),
                "title": post.get("title"),
                "text": text,
                "handle": resolved_handle,
            },
            log_path,
        )
        return result

    resolved_credentials = credentials or load_credentials()
    session = create_session(resolved_credentials)
    blob = None
    external_embed = None
    if post.get("image_url"):
        image_bytes, mime_type = download_image(post["image_url"])
        image_bytes, mime_type = optimize_image_for_bluesky(image_bytes, mime_type)
        blob = upload_blob(image_bytes, mime_type, session["accessJwt"])
    if post.get("url"):
        external_embed = build_external_embed(post, blob=blob)
    response = create_post(
        text=text,
        did=session["did"],
        access_jwt=session["accessJwt"],
        blob=blob if not external_embed else None,
        external_embed=external_embed,
    )
    event = {
        "logged_at": utc_now_iso(),
        "status": "published",
        "shirt_id": post.get("shirt_id"),
        "title": post.get("title"),
        "text": text,
        "handle": resolved_handle,
        "uri": response.get("uri"),
        "cid": response.get("cid"),
    }
    log_publish_event(event, log_path)
    result.update(event)
    return result


def build_bluesky_status(post, max_length=MAX_POST_LENGTH):
    caption = strip_urls(post.get("caption") or "").strip()
    if len(caption) <= max_length:
        return caption

    headline = (post.get("headline") or post.get("title") or "").strip()
    hashtags = " ".join(post.get("hashtags") or [])
    compact = " ".join(part for part in [headline, hashtags] if part)
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


def create_session(credentials):
    payload = {
        "identifier": credentials["handle"],
        "password": credentials["app_password"],
    }
    response = json_request(
        CREATE_SESSION_URL,
        payload,
        headers={"Content-Type": "application/json"},
    )
    if not response.get("accessJwt") or not response.get("did"):
        raise BlueskyPublisherError(f"Bluesky session response missing expected fields: {response}")
    return response


def create_post(text, did, access_jwt, blob=None, external_embed=None):
    record = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    if external_embed:
        record["embed"] = external_embed
    elif blob:
        record["embed"] = {
            "$type": "app.bsky.embed.images",
            "images": [
                {
                    "alt": "ShirtClawd product image",
                    "image": blob,
                }
            ],
        }

    payload = {
        "repo": did,
        "collection": "app.bsky.feed.post",
        "record": record,
    }
    response = json_request(
        CREATE_RECORD_URL,
        payload,
        headers={
            "Authorization": f"Bearer {access_jwt}",
            "Content-Type": "application/json",
        },
    )
    if not response.get("uri"):
        raise BlueskyPublisherError(f"Unexpected Bluesky createRecord response: {response}")
    return response


def build_external_embed(post, blob=None):
    description = trim_text(strip_urls(post.get("caption") or post.get("headline") or ""), 280)
    external = {
        "uri": post.get("url"),
        "title": (post.get("headline") or post.get("title") or "Third String Shirts").strip(),
        "description": description,
    }
    if blob:
        external["thumb"] = blob
    return {
        "$type": "app.bsky.embed.external",
        "external": external,
    }


def upload_blob(image_bytes, mime_type, access_jwt):
    request = Request(
        UPLOAD_BLOB_URL,
        data=image_bytes,
        headers={
            "Authorization": f"Bearer {access_jwt}",
            "Content-Type": mime_type,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise BlueskyPublisherError(f"Bluesky blob upload failed: {exc.code} {error_body}") from exc
    except URLError as exc:
        raise BlueskyPublisherError(f"Bluesky blob upload failed: {exc}") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BlueskyPublisherError(f"Bluesky blob upload returned invalid JSON: {exc}") from exc

    blob = payload.get("blob")
    if not blob:
        raise BlueskyPublisherError(f"Bluesky blob upload response missing blob: {payload}")
    return blob


def json_request(url, payload, headers=None):
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers or {"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise BlueskyPublisherError(f"Bluesky API request failed: {exc.code} {error_body}") from exc
    except URLError as exc:
        raise BlueskyPublisherError(f"Bluesky API request failed: {exc}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BlueskyPublisherError(f"Bluesky API returned invalid JSON: {exc}") from exc


def download_image(image_url):
    request = Request(image_url, method="GET")
    try:
        with urlopen(request, timeout=30) as response:
            payload = response.read()
            content_type = response.headers.get_content_type()
    except (HTTPError, URLError) as exc:
        raise BlueskyPublisherError(f"Failed to download image from {image_url}: {exc}") from exc

    mime_type = content_type or mimetypes.guess_type(image_url)[0] or "image/jpeg"
    return payload, mime_type


def optimize_image_for_bluesky(image_bytes, mime_type, max_bytes=MAX_BLOB_BYTES):
    if len(image_bytes) <= max_bytes:
        return image_bytes, mime_type

    optimized = resize_image_with_sips(image_bytes, mime_type, max_bytes=max_bytes)
    if optimized:
        return optimized
    return image_bytes, mime_type


def resize_image_with_sips(image_bytes, mime_type, max_bytes=MAX_BLOB_BYTES):
    sips_path = shutil.which("sips")
    if not sips_path:
        return None

    source_suffix = suffix_for_mime_type(mime_type)
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / f"source{source_suffix}"
        input_path.write_bytes(image_bytes)

        current_path = input_path
        for width in BLUESKY_RESIZE_WIDTHS:
            output_path = Path(tmpdir) / f"scaled-{width}.jpg"
            command = [
                sips_path,
                "-s",
                "format",
                "jpeg",
                "-Z",
                str(width),
                str(current_path),
                "--out",
                str(output_path),
            ]
            try:
                subprocess.run(command, check=True, capture_output=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                return None

            optimized_bytes = output_path.read_bytes()
            if len(optimized_bytes) <= max_bytes:
                return optimized_bytes, "image/jpeg"
            current_path = output_path

    return None


def suffix_for_mime_type(mime_type):
    guessed = mimetypes.guess_extension(mime_type or "")
    if guessed:
        return guessed
    return ".img"


def log_publish_event(event, path=DEFAULT_PUBLISH_LOG_PATH):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a") as handle:
        handle.write(json.dumps(event) + "\n")


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()
