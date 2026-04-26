import json
import os
import re
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from bot.bluesky_discovery import clean_text, human_age, int_value, parse_datetime, relevance_points


GRAPH_BASE_URL = "https://graph.facebook.com/v24.0"
DEFAULT_SEARCH_LIMIT = 25
DEFAULT_MAX_AGE_DAYS = 7
DEFAULT_MAX_HASHTAGS = 6


class InstagramDiscoveryError(RuntimeError):
    pass


def load_credentials(env=None):
    source = env or os.environ
    credentials = {
        "access_token": source.get("INSTAGRAM_ACCESS_TOKEN"),
        "account_id": source.get("INSTAGRAM_BUSINESS_ACCOUNT_ID"),
    }
    missing = [name for name, value in credentials.items() if not value]
    if missing:
        raise InstagramDiscoveryError(f"Missing Instagram credentials: {', '.join(missing)}")
    return credentials


def find_reply_candidates(
    hashtags,
    max_candidates=3,
    search_limit=DEFAULT_SEARCH_LIMIT,
    max_age_days=DEFAULT_MAX_AGE_DAYS,
    now=None,
    credentials=None,
    resolve_hashtag_id_fn=None,
    search_recent_media_fn=None,
):
    resolved_credentials = credentials or (None if resolve_hashtag_id_fn and search_recent_media_fn else load_credentials())
    resolver = resolve_hashtag_id_fn or resolve_hashtag_id
    searcher = search_recent_media_fn or search_recent_media
    resolved_now = parse_datetime(now) if now else datetime.now(timezone.utc)
    by_id = {}
    errors = []

    for hashtag in normalize_hashtags(hashtags):
        try:
            hashtag_id = resolver(hashtag, credentials=resolved_credentials)
            media_items = searcher(hashtag_id, hashtag=hashtag, limit=search_limit, credentials=resolved_credentials)
        except InstagramDiscoveryError as exc:
            errors.append(str(exc))
            continue

        for media in media_items:
            candidate = candidate_from_media(
                media,
                hashtag=hashtag,
                now=resolved_now,
                max_age_days=max_age_days,
            )
            if not candidate:
                continue
            existing = by_id.get(candidate["uri"])
            if existing:
                existing.setdefault("matched_queries", []).append(f"#{hashtag}")
                existing["score"] = max(existing["score"], candidate["score"])
                continue
            by_id[candidate["uri"]] = candidate

    if not by_id and errors:
        raise InstagramDiscoveryError("; ".join(errors[:3]))
    if not by_id:
        return manual_hashtag_candidates(hashtags, max_candidates=max_candidates)

    candidates = sorted(by_id.values(), key=lambda item: (-item["score"], item.get("age_hours", 0), item["uri"]))
    return candidates[:max_candidates]


def resolve_hashtag_id(hashtag, credentials=None):
    resolved_credentials = credentials or load_credentials()
    response = get_json_request(
        f"{GRAPH_BASE_URL}/ig_hashtag_search",
        {
            "user_id": resolved_credentials["account_id"],
            "q": hashtag,
            "access_token": resolved_credentials["access_token"],
        },
    )
    data = response.get("data", [])
    if not isinstance(data, list) or not data or not data[0].get("id"):
        raise InstagramDiscoveryError(f"No Instagram hashtag id found for #{hashtag}")
    return data[0]["id"]


def search_recent_media(hashtag_id, hashtag="", limit=DEFAULT_SEARCH_LIMIT, credentials=None):
    resolved_credentials = credentials or load_credentials()
    response = get_json_request(
        f"{GRAPH_BASE_URL}/{hashtag_id}/recent_media",
        {
            "user_id": resolved_credentials["account_id"],
            "fields": "id,caption,comments_count,like_count,media_type,media_url,permalink,timestamp",
            "limit": max(1, min(int(limit or DEFAULT_SEARCH_LIMIT), 50)),
            "access_token": resolved_credentials["access_token"],
        },
    )
    media = response.get("data", [])
    if not isinstance(media, list):
        raise InstagramDiscoveryError(f"Unexpected Instagram hashtag response for #{hashtag}: {response}")
    return media


def candidate_from_media(media, hashtag, now, max_age_days=DEFAULT_MAX_AGE_DAYS):
    if not isinstance(media, dict):
        return None
    media_id = str(media.get("id") or "")
    permalink = str(media.get("permalink") or "")
    caption = clean_text(media.get("caption") or "")
    created_at = parse_datetime(media.get("timestamp"))
    if not media_id or not permalink or not created_at:
        return None

    age_hours = max(0.0, (now - created_at).total_seconds() / 3600)
    if age_hours > max_age_days * 24:
        return None

    like_count = int_value(media.get("like_count"))
    comment_count = int_value(media.get("comments_count"))
    score = score_candidate(
        caption=caption,
        hashtag=hashtag,
        age_hours=age_hours,
        like_count=like_count,
        comment_count=comment_count,
        max_age_days=max_age_days,
    )
    candidate = {
        "platform": "instagram",
        "url": permalink,
        "uri": media_id,
        "cid": "",
        "author_handle": "",
        "author_display_name": f"Instagram #{hashtag}",
        "author_did": "",
        "text": caption,
        "created_at": created_at.isoformat(),
        "age_hours": round(age_hours, 2),
        "reply_count": comment_count,
        "comment_count": comment_count,
        "repost_count": 0,
        "like_count": like_count,
        "quote_count": 0,
        "query": f"#{hashtag}",
        "matched_queries": [f"#{hashtag}"],
        "score": round(score, 2),
        "media_type": media.get("media_type") or "",
    }
    candidate["reason"] = describe_candidate(candidate)
    return candidate


def score_candidate(caption, hashtag, age_hours, like_count=0, comment_count=0, max_age_days=DEFAULT_MAX_AGE_DAYS):
    max_age_hours = max(max_age_days * 24, 1)
    recency_score = max(0, 45 - (age_hours / max_age_hours) * 45)
    engagement_score = min(like_count, 100) * 0.25 + min(comment_count, 40) * 0.8
    relevance_score = relevance_points(caption, hashtag)
    return recency_score + engagement_score + relevance_score


def describe_candidate(candidate):
    age = human_age(candidate.get("age_hours", 0))
    return (
        f"Recent {age} Instagram media from {candidate.get('query')} "
        f"with {candidate.get('like_count', 0)} likes and {candidate.get('comment_count', 0)} comments."
    )


def build_hashtags(topic, post=None, queries=None, max_hashtags=DEFAULT_MAX_HASHTAGS):
    values = []
    values.append(f"Colorado {topic}")
    values.append(f"Denver {topic}")
    values.append(topic)
    values.extend(topic_tag_variants(topic))
    for query in queries or []:
        values.extend(query_tag_variants(query))
    values.extend(filter_discovery_post_tags((post or {}).get("hashtags") or []))
    return normalize_hashtags(values)[:max_hashtags]


def manual_hashtag_candidates(hashtags, max_candidates=3):
    candidates = []
    for index, hashtag in enumerate(normalize_hashtags(hashtags)[:max_candidates], start=1):
        url = instagram_hashtag_url(hashtag)
        candidate = {
            "platform": "instagram",
            "url": url,
            "uri": url,
            "cid": "",
            "author_handle": "",
            "author_display_name": f"Instagram #{hashtag}",
            "author_did": "",
            "text": "Manual Instagram hashtag review target.",
            "created_at": "",
            "age_hours": 0,
            "reply_count": 0,
            "comment_count": 0,
            "repost_count": 0,
            "like_count": 0,
            "quote_count": 0,
            "query": f"#{hashtag}",
            "matched_queries": [f"#{hashtag}"],
            "score": max(1, 10 - index),
            "target_search_url": url,
            "manual_review": True,
        }
        candidate["reason"] = (
            f"Manual Instagram hashtag review target for #{hashtag}; choose a specific recent post before approving."
        )
        candidates.append(candidate)
    return candidates


def instagram_hashtag_url(hashtag):
    return f"https://www.instagram.com/explore/tags/{hashtag}/"


def topic_tag_variants(topic):
    tokens = meaningful_tokens(topic)
    variants = []
    if tokens:
        variants.append(tokens[-1])
        variants.append(f"colorado {tokens[-1]}")
        variants.append(f"denver {tokens[-1]}")
    return variants


def query_tag_variants(query):
    tokens = meaningful_tokens(query)
    if not tokens:
        return []
    if len(tokens) <= 2:
        return [" ".join(tokens)]
    local = [token for token in tokens if token in {"colorado", "denver"}]
    topic = [token for token in tokens if token not in {"colorado", "denver"}]
    if local and topic:
        return [f"{local[0]} {topic[-1]}"]
    return [tokens[-1]]


def meaningful_tokens(text):
    stopwords = {"memes", "meme", "overrated", "weekend", "plans", "plan", "this", "against"}
    return [token for token in re.findall(r"[a-z0-9]+", str(text or "").lower()) if token not in stopwords]


def filter_discovery_post_tags(tags):
    blocked_fragments = ("thirdstring", "coloradansagainst", "regionalsarcasm", "couchpotato")
    filtered = []
    for tag in tags:
        normalized = re.sub(r"[^a-z0-9_]+", "", str(tag or "").lower().lstrip("#"))
        if not normalized or any(fragment in normalized for fragment in blocked_fragments):
            continue
        filtered.append(tag)
    return filtered


def normalize_hashtags(values):
    normalized = []
    seen = set()
    for value in values:
        text = str(value or "").strip().lower()
        if not text:
            continue
        chunks = re.findall(r"#?[a-z0-9][a-z0-9_ ]*", text)
        for chunk in chunks:
            tag = re.sub(r"[^a-z0-9_]+", "", chunk.lstrip("#").replace(" ", ""))
            if len(tag) < 2 or tag in seen:
                continue
            seen.add(tag)
            normalized.append(tag)
    return normalized


def get_json_request(url, payload):
    request = Request(f"{url}?{urlencode(payload)}", method="GET")
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise InstagramDiscoveryError(f"Instagram discovery failed: {exc.code} {error_body}") from exc
    except URLError as exc:
        raise InstagramDiscoveryError(f"Instagram discovery failed: {exc}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InstagramDiscoveryError(f"Instagram discovery returned invalid JSON: {exc}") from exc
