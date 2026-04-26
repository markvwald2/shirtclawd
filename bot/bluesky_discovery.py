import json
import re
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


BLUESKY_APP_BASE_URL = "https://bsky.app"
BLUESKY_SEARCH_POSTS_URL = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"
DEFAULT_USER_AGENT = "ShirtClawd/1.0 (+https://thirdstringshirts.com)"
DEFAULT_SEARCH_LIMIT = 20
DEFAULT_MAX_AGE_DAYS = 21


class BlueskyDiscoveryError(RuntimeError):
    pass


def find_reply_candidates(
    queries,
    max_candidates=3,
    search_limit=DEFAULT_SEARCH_LIMIT,
    max_age_days=DEFAULT_MAX_AGE_DAYS,
    now=None,
    exclude_handles=None,
    exclude_dids=None,
    search_posts_fn=None,
):
    searcher = search_posts_fn or search_posts
    resolved_now = parse_datetime(now) if now else datetime.now(timezone.utc)
    excluded_handles = {str(handle).lower() for handle in (exclude_handles or []) if handle}
    excluded_dids = {str(did).lower() for did in (exclude_dids or []) if did}
    by_uri = {}

    for query in queries:
        if not str(query or "").strip():
            continue
        posts = searcher(query, limit=search_limit)
        for post in posts:
            candidate = candidate_from_post(
                post,
                query=query,
                now=resolved_now,
                max_age_days=max_age_days,
                exclude_handles=excluded_handles,
                exclude_dids=excluded_dids,
            )
            if not candidate:
                continue
            existing = by_uri.get(candidate["uri"])
            if existing:
                existing.setdefault("matched_queries", []).append(query)
                existing["score"] = max(existing["score"], candidate["score"])
                continue
            by_uri[candidate["uri"]] = candidate

    candidates = sorted(by_uri.values(), key=lambda item: (-item["score"], item.get("age_hours", 0), item["uri"]))
    return candidates[:max_candidates]


def search_posts(query, limit=DEFAULT_SEARCH_LIMIT):
    params = {
        "q": query,
        "limit": max(1, min(int(limit or DEFAULT_SEARCH_LIMIT), 100)),
        "sort": "latest",
    }
    payload = get_json_request(BLUESKY_SEARCH_POSTS_URL, params)
    posts = payload.get("posts", [])
    if not isinstance(posts, list):
        raise BlueskyDiscoveryError(f"Unexpected Bluesky search response: {payload}")
    return posts


def candidate_from_post(
    post,
    query,
    now,
    max_age_days=DEFAULT_MAX_AGE_DAYS,
    exclude_handles=None,
    exclude_dids=None,
):
    if not isinstance(post, dict):
        return None
    author = post.get("author") or {}
    record = post.get("record") or {}
    uri = str(post.get("uri") or "")
    cid = str(post.get("cid") or "")
    handle = str(author.get("handle") or "")
    did = str(author.get("did") or "")
    text = clean_text(record.get("text") or "")
    created_at = parse_datetime(record.get("createdAt") or post.get("indexedAt"))

    if not uri or not cid or not handle or not created_at:
        return None
    if is_reply_record(record):
        return None
    if handle.lower() in (exclude_handles or set()) or did.lower() in (exclude_dids or set()):
        return None

    age_hours = max(0.0, (now - created_at).total_seconds() / 3600)
    if age_hours > max_age_days * 24:
        return None

    url = bsky_post_url(handle, uri)
    if not url:
        return None

    reply_count = int_value(post.get("replyCount"))
    repost_count = int_value(post.get("repostCount"))
    like_count = int_value(post.get("likeCount"))
    quote_count = int_value(post.get("quoteCount"))
    score = score_candidate(
        text=text,
        query=query,
        age_hours=age_hours,
        reply_count=reply_count,
        repost_count=repost_count,
        like_count=like_count,
        quote_count=quote_count,
        max_age_days=max_age_days,
        handle=handle,
    )

    candidate = {
        "url": url,
        "uri": uri,
        "cid": cid,
        "author_handle": handle,
        "author_display_name": author.get("displayName") or handle,
        "author_did": did,
        "text": text,
        "created_at": created_at.isoformat(),
        "age_hours": round(age_hours, 2),
        "reply_count": reply_count,
        "repost_count": repost_count,
        "like_count": like_count,
        "quote_count": quote_count,
        "query": query,
        "matched_queries": [query],
        "score": round(score, 2),
    }
    candidate["reason"] = describe_candidate(candidate)
    return candidate


def score_candidate(
    text,
    query,
    age_hours,
    reply_count,
    repost_count,
    like_count,
    quote_count,
    max_age_days=DEFAULT_MAX_AGE_DAYS,
    handle="",
):
    max_age_hours = max(max_age_days * 24, 1)
    recency_score = max(0, 45 - (age_hours / max_age_hours) * 45)
    engagement_score = min(like_count, 40) * 0.45 + min(repost_count, 20) * 1.1 + min(quote_count, 10) * 1.2
    reply_lane_bonus = 8 if reply_count <= 3 else max(0, 8 - (reply_count - 3) * 0.7)
    relevance_score = relevance_points(text, query)
    account_bonus = 3 if local_handle_hint(handle) else 0
    return recency_score + engagement_score + reply_lane_bonus + relevance_score + account_bonus


def relevance_points(text, query):
    text_tokens = set(tokenize(text))
    query_tokens = [token for token in tokenize(query) if len(token) > 2]
    if not query_tokens:
        return 0
    hits = sum(1 for token in query_tokens if token in text_tokens)
    return min(20, hits * 5)


def local_handle_hint(handle):
    normalized = str(handle or "").lower()
    return any(marker in normalized for marker in ("denver", "colorado", "westword", "5280"))


def describe_candidate(candidate):
    age = human_age(candidate.get("age_hours", 0))
    engagement = (
        f"{candidate.get('like_count', 0)} likes, "
        f"{candidate.get('repost_count', 0)} reposts, "
        f"{candidate.get('reply_count', 0)} replies"
    )
    return (
        f"Fresh {age} post from {candidate.get('author_display_name') or candidate.get('author_handle')} "
        f"matching `{candidate.get('query')}` with {engagement}."
    )


def human_age(age_hours):
    try:
        hours = float(age_hours)
    except (TypeError, ValueError):
        return "recent"
    if hours < 1:
        return "under 1h old"
    if hours < 24:
        return f"{int(round(hours))}h old"
    days = max(1, int(round(hours / 24)))
    return f"{days}d old"


def bsky_post_url(handle, uri):
    rkey = rkey_from_at_uri(uri)
    if not rkey:
        return ""
    return f"{BLUESKY_APP_BASE_URL}/profile/{handle}/post/{rkey}"


def rkey_from_at_uri(uri):
    parsed = urlparse(str(uri or ""))
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.scheme != "at" or len(parts) != 2 or parts[0] != "app.bsky.feed.post":
        return ""
    return parts[1]


def is_reply_record(record):
    reply = (record or {}).get("reply")
    return isinstance(reply, dict) and bool(reply)


def parse_datetime(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def clean_text(text):
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    return cleaned


def tokenize(text):
    return re.findall(r"[a-z0-9]+", str(text or "").lower())


def int_value(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def get_json_request(url, payload, headers=None):
    request_url = f"{url}?{urlencode(payload)}"
    request = Request(
        request_url,
        headers=headers
        or {
            "Accept": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise BlueskyDiscoveryError(f"Bluesky search failed: {exc.code} {error_body}") from exc
    except URLError as exc:
        raise BlueskyDiscoveryError(f"Bluesky search failed: {exc}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BlueskyDiscoveryError(f"Bluesky search returned invalid JSON: {exc}") from exc
