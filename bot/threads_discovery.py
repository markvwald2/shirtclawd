import json
import os
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen

from bot.bluesky_discovery import clean_text, human_age, int_value, parse_datetime, relevance_points


THREADS_BASE_URL = "https://graph.threads.net/v1.0"
THREADS_KEYWORD_SEARCH_URL = f"{THREADS_BASE_URL}/keyword_search"
DEFAULT_SEARCH_LIMIT = 25
DEFAULT_MAX_AGE_DAYS = 21


class ThreadsDiscoveryError(RuntimeError):
    pass


def load_credentials(env=None):
    source = env or os.environ
    access_token = source.get("THREADS_ACCESS_TOKEN")
    if not access_token:
        raise ThreadsDiscoveryError("Missing Threads credentials: access_token")
    return {"access_token": access_token}


def find_reply_candidates(
    queries,
    max_candidates=3,
    search_limit=DEFAULT_SEARCH_LIMIT,
    max_age_days=DEFAULT_MAX_AGE_DAYS,
    now=None,
    exclude_usernames=None,
    search_media_fn=None,
    credentials=None,
):
    searcher = search_media_fn or search_threads_media
    resolved_now = parse_datetime(now) if now else datetime.now(timezone.utc)
    excluded = {normalize_username(username) for username in (exclude_usernames or []) if username}
    by_id = {}

    for query in queries:
        if not str(query or "").strip():
            continue
        posts = searcher(query, limit=search_limit, credentials=credentials)
        for post in posts:
            candidate = candidate_from_media(
                post,
                query=query,
                now=resolved_now,
                max_age_days=max_age_days,
                exclude_usernames=excluded,
            )
            if not candidate:
                continue
            existing = by_id.get(candidate["uri"])
            if existing:
                existing.setdefault("matched_queries", []).append(query)
                existing["score"] = max(existing["score"], candidate["score"])
                continue
            by_id[candidate["uri"]] = candidate

    candidates = sorted(by_id.values(), key=lambda item: (-item["score"], item.get("age_hours", 0), item["uri"]))
    if candidates:
        return candidates[:max_candidates]
    return manual_search_candidates(queries, max_candidates=max_candidates)


def search_threads_media(query, limit=DEFAULT_SEARCH_LIMIT, credentials=None):
    resolved_credentials = credentials or load_credentials()
    payload = {
        "q": query,
        "search_type": "RECENT",
        "fields": "id,text,media_type,permalink,timestamp,username,has_replies,is_quote_post,is_reply",
        "limit": max(1, min(int(limit or DEFAULT_SEARCH_LIMIT), 100)),
        "access_token": resolved_credentials["access_token"],
    }
    response = get_json_request(THREADS_KEYWORD_SEARCH_URL, payload)
    posts = response.get("data", [])
    if not isinstance(posts, list):
        raise ThreadsDiscoveryError(f"Unexpected Threads search response: {response}")
    return posts


def candidate_from_media(media, query, now, max_age_days=DEFAULT_MAX_AGE_DAYS, exclude_usernames=None):
    if not isinstance(media, dict):
        return None
    media_id = str(media.get("id") or "")
    permalink = str(media.get("permalink") or "")
    username = normalize_username(media.get("username") or "")
    text = clean_text(media.get("text") or "")
    created_at = parse_datetime(media.get("timestamp"))
    if not media_id or not permalink or not username or not created_at:
        return None
    if username in (exclude_usernames or set()):
        return None
    if media.get("is_reply") or media.get("is_quote_post"):
        return None

    age_hours = max(0.0, (now - created_at).total_seconds() / 3600)
    if age_hours > max_age_days * 24:
        return None

    has_replies = bool(media.get("has_replies"))
    score = score_candidate(
        text=text,
        query=query,
        age_hours=age_hours,
        has_replies=has_replies,
        max_age_days=max_age_days,
    )
    candidate = {
        "platform": "threads",
        "url": permalink,
        "uri": media_id,
        "cid": "",
        "author_handle": username,
        "author_display_name": f"@{username}",
        "author_did": "",
        "text": text,
        "created_at": created_at.isoformat(),
        "age_hours": round(age_hours, 2),
        "reply_count": 1 if has_replies else 0,
        "repost_count": 0,
        "like_count": 0,
        "quote_count": 0,
        "query": query,
        "matched_queries": [query],
        "score": round(score, 2),
        "media_type": media.get("media_type") or "",
        "has_replies": has_replies,
    }
    candidate["reason"] = describe_candidate(candidate)
    return candidate


def score_candidate(text, query, age_hours, has_replies=False, max_age_days=DEFAULT_MAX_AGE_DAYS):
    max_age_hours = max(max_age_days * 24, 1)
    recency_score = max(0, 48 - (age_hours / max_age_hours) * 48)
    reply_lane_bonus = 4 if has_replies else 10
    relevance_score = relevance_points(text, query)
    return recency_score + reply_lane_bonus + relevance_score


def describe_candidate(candidate):
    age = human_age(candidate.get("age_hours", 0))
    reply_state = "already has replies" if candidate.get("has_replies") else "has no visible replies yet"
    return (
        f"Fresh {age} Threads post from {candidate.get('author_display_name')} "
        f"matching `{candidate.get('query')}`; {reply_state}."
    )


def normalize_username(username):
    return str(username or "").strip().lstrip("@").lower()


def manual_search_candidates(queries, max_candidates=3):
    candidates = []
    for index, query in enumerate([query for query in queries if str(query or "").strip()][:max_candidates], start=1):
        url = threads_search_url(query)
        candidate = {
            "platform": "threads",
            "url": url,
            "uri": url,
            "cid": "",
            "author_handle": "",
            "author_display_name": f"Threads search: {query}",
            "author_did": "",
            "text": "Manual Threads search review target.",
            "created_at": "",
            "age_hours": 0,
            "reply_count": 0,
            "repost_count": 0,
            "like_count": 0,
            "quote_count": 0,
            "query": query,
            "matched_queries": [query],
            "score": max(1, 10 - index),
            "target_search_url": url,
            "manual_review": True,
        }
        candidate["reason"] = (
            f"Manual Threads search target for `{query}`; choose a specific recent post before approving."
        )
        candidates.append(candidate)
    return candidates


def threads_search_url(query):
    return f"https://www.threads.net/search?q={quote_plus(str(query or '').strip())}"


def get_json_request(url, payload):
    request = Request(f"{url}?{urlencode(payload)}", method="GET")
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise ThreadsDiscoveryError(f"Threads search failed: {exc.code} {error_body}") from exc
    except URLError as exc:
        raise ThreadsDiscoveryError(f"Threads search failed: {exc}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ThreadsDiscoveryError(f"Threads search returned invalid JSON: {exc}") from exc
