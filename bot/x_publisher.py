import base64
import hashlib
import hmac
import json
import mimetypes
import os
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlparse
from urllib.request import Request, urlopen


X_POST_URL = "https://api.x.com/2/tweets"
X_MEDIA_UPLOAD_URL = "https://upload.twitter.com/1.1/media/upload.json"
DEFAULT_PUBLISH_LOG_PATH = Path("data/x_publish_log.jsonl")
DEFAULT_X_HANDLE = "@3rdStringShirts"


class XPublisherError(RuntimeError):
    pass


def load_credentials(env=None):
    source = env or os.environ
    credentials = {
        "api_key": source.get("X_API_KEY"),
        "api_key_secret": source.get("X_API_KEY_SECRET"),
        "access_token": source.get("X_ACCESS_TOKEN"),
        "access_token_secret": source.get("X_ACCESS_TOKEN_SECRET"),
    }
    missing = [name for name, value in credentials.items() if not value]
    if missing:
        raise XPublisherError(f"Missing X credentials: {', '.join(missing)}")
    return credentials


def load_posts(path):
    with Path(path).open() as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise XPublisherError("Post file must contain a JSON array.")
    return payload


def select_post(posts, index=None, shirt_id=None):
    if shirt_id:
        for post in posts:
            if post.get("shirt_id") == shirt_id:
                return post
        raise XPublisherError(f"No post found for shirt_id={shirt_id}")

    resolved_index = 0 if index is None else index
    if resolved_index < 0 or resolved_index >= len(posts):
        raise XPublisherError(f"Post index {resolved_index} is out of range for {len(posts)} posts.")
    return posts[resolved_index]


def publish_post(post, dry_run=True, credentials=None, log_path=DEFAULT_PUBLISH_LOG_PATH, handle=DEFAULT_X_HANDLE):
    text = build_x_status(post)
    result = {
        "mode": "dry_run" if dry_run else "publish",
        "shirt_id": post.get("shirt_id"),
        "title": post.get("title"),
        "text": text,
        "image_url": post.get("image_url"),
        "platform": "x",
        "handle": handle,
    }

    if dry_run:
        log_publish_event(
            {
                "logged_at": utc_now_iso(),
                "status": "dry_run",
                "shirt_id": post.get("shirt_id"),
                "title": post.get("title"),
                "text": text,
                "handle": handle,
            },
            log_path,
        )
        return result

    resolved_credentials = credentials or load_credentials()
    image_bytes, mime_type = download_image(post["image_url"])
    media_id = upload_media(image_bytes, mime_type, resolved_credentials)
    response = create_post(text, media_id, resolved_credentials)
    event = {
        "logged_at": utc_now_iso(),
        "status": "published",
        "shirt_id": post.get("shirt_id"),
        "title": post.get("title"),
        "text": text,
        "handle": handle,
        "media_id": media_id,
        "tweet_id": response.get("data", {}).get("id"),
        "tweet_text": response.get("data", {}).get("text"),
    }
    log_publish_event(event, log_path)
    result.update(event)
    return result


def build_x_status(post, max_length=280):
    caption = (post.get("caption") or "").strip()
    if len(caption) <= max_length:
        return caption

    headline = (post.get("headline") or post.get("title") or "").strip()
    url = (post.get("url") or "").strip()
    hashtags = " ".join(post.get("hashtags") or [])
    parts = [part for part in [headline, url, hashtags] if part]
    compact = " ".join(parts)
    if len(compact) <= max_length:
        return compact

    reserve = len(url) + len(hashtags) + 2 if url or hashtags else 0
    available = max_length - reserve
    trimmed_headline = trim_text(headline, max(available, 0))
    final_parts = [part for part in [trimmed_headline, url, hashtags] if part]
    final_text = " ".join(final_parts).strip()
    if len(final_text) <= max_length:
        return final_text

    return trim_text(caption, max_length)


def trim_text(text, limit):
    if len(text) <= limit:
        return text
    if limit <= 1:
        return text[:limit]
    return text[: limit - 1].rstrip() + "…"


def download_image(image_url):
    request = Request(image_url, method="GET")
    try:
        with urlopen(request, timeout=30) as response:
            payload = response.read()
            content_type = response.headers.get_content_type()
    except (HTTPError, URLError) as exc:
        raise XPublisherError(f"Failed to download image from {image_url}: {exc}") from exc

    mime_type = content_type or mimetypes.guess_type(image_url)[0] or "image/jpeg"
    return payload, mime_type


def upload_media(image_bytes, mime_type, credentials):
    boundary = f"clawdbot-{uuid.uuid4().hex}"
    body = build_multipart_body(
        boundary,
        [
            (
                "media",
                "shirtclawd-image",
                mime_type,
                image_bytes,
            )
        ],
    )
    response = signed_request(
        method="POST",
        url=X_MEDIA_UPLOAD_URL,
        credentials=credentials,
        body=body,
        content_type=f"multipart/form-data; boundary={boundary}",
        operation_name="media upload",
    )
    media_id = response.get("media_id_string") or str(response.get("media_id", ""))
    if not media_id:
        raise XPublisherError(f"Media upload did not return media_id: {response}")
    return media_id


def create_post(text, media_id, credentials):
    payload = {"text": text}
    if media_id:
        payload["media"] = {"media_ids": [media_id]}

    response = signed_request(
        method="POST",
        url=X_POST_URL,
        credentials=credentials,
        body=json.dumps(payload).encode("utf-8"),
        content_type="application/json",
        operation_name="tweet creation",
    )
    if "data" not in response:
        raise XPublisherError(f"Unexpected X API response: {response}")
    return response


def signed_request(method, url, credentials, body=None, content_type=None, operation_name="request"):
    auth_header = build_oauth_header(method, url, credentials)
    request = Request(
        url,
        data=body,
        headers={
            "Authorization": auth_header,
            "Content-Type": content_type or "application/octet-stream",
        },
        method=method,
    )
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        details = error_body.strip() or "<empty response body>"
        raise XPublisherError(
            f"X API {operation_name} failed: {exc.code} {method.upper()} {url} {details}"
        ) from exc
    except URLError as exc:
        raise XPublisherError(f"X API {operation_name} failed: {method.upper()} {url} {exc}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise XPublisherError(f"X API returned invalid JSON: {exc}") from exc


def build_oauth_header(method, url, credentials):
    oauth_params = {
        "oauth_consumer_key": credentials["api_key"],
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": credentials["access_token"],
        "oauth_version": "1.0",
    }
    oauth_params["oauth_signature"] = build_oauth_signature(method, url, oauth_params, credentials)
    header_parts = [
        f'{percent_encode(key)}="{percent_encode(value)}"'
        for key, value in sorted(oauth_params.items())
    ]
    return "OAuth " + ", ".join(header_parts)


def build_oauth_signature(method, url, oauth_params, credentials):
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    query_params = parse_qsl(parsed.query, keep_blank_values=True)
    signature_params = list(query_params) + list(oauth_params.items())
    normalized = "&".join(
        f"{percent_encode(key)}={percent_encode(value)}"
        for key, value in sorted((str(k), str(v)) for k, v in signature_params)
    )
    base_string = "&".join(
        [
            method.upper(),
            percent_encode(base_url),
            percent_encode(normalized),
        ]
    )
    signing_key = (
        f"{percent_encode(credentials['api_key_secret'])}"
        f"&{percent_encode(credentials['access_token_secret'])}"
    )
    digest = hmac.new(signing_key.encode("utf-8"), base_string.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("utf-8")


def build_multipart_body(boundary, files):
    chunks = []
    for field_name, filename, mime_type, payload in files:
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                (
                    f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
                ).encode("utf-8"),
                f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"),
                payload,
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks)


def percent_encode(value):
    return quote(str(value), safe="~-._")


def log_publish_event(event, path=DEFAULT_PUBLISH_LOG_PATH):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a") as handle:
        handle.write(json.dumps(event) + "\n")


def utc_now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
