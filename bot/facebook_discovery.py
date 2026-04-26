import json
from pathlib import Path
from urllib.parse import quote_plus

from bot.bluesky_discovery import relevance_points


DEFAULT_FACEBOOK_TARGETS_PATH = Path("config/facebook_discovery_targets.json")


DEFAULT_TARGETS = [
    {
        "name": "Westword",
        "url": "https://www.facebook.com/DenverWestword",
        "keywords": ["denver", "colorado", "brewery", "beer", "running", "events", "culture", "hiking"],
        "notes": "Local culture and event coverage; useful for Denver argument-starter replies.",
    },
    {
        "name": "The Denver Post",
        "url": "https://www.facebook.com/denverpost",
        "keywords": ["denver", "colorado", "beer", "brewery", "hiking", "news", "outdoors"],
        "notes": "Broad Colorado news account with culture and outdoors posts.",
    },
    {
        "name": "5280 Magazine",
        "url": "https://www.facebook.com/5280magazine",
        "keywords": ["denver", "colorado", "culture", "outdoors", "hiking", "food", "beer"],
        "notes": "Colorado lifestyle account; good for local sacred-cow topics.",
    },
    {
        "name": "Visit Denver",
        "url": "https://www.facebook.com/VisitDenver",
        "keywords": ["denver", "weekend", "events", "beer", "hiking", "outdoors", "tourism"],
        "notes": "Tourism/event account; useful when the topic is weekend plans or local rituals.",
    },
    {
        "name": "9NEWS",
        "url": "https://www.facebook.com/ilike9news",
        "keywords": ["colorado", "denver", "traffic", "weather", "outdoors", "news"],
        "notes": "High-reach local news page; review carefully before joining a serious thread.",
    },
]


def find_reply_candidates(queries, topic="", max_candidates=3, targets_path=DEFAULT_FACEBOOK_TARGETS_PATH):
    targets = load_targets(targets_path)
    query_text = " ".join(str(query or "") for query in queries)
    candidates = []

    for target in targets:
        score = score_target(target, topic=topic, query_text=query_text)
        if score <= 0:
            continue
        search_query = best_search_query(target, topic, queries)
        candidate = {
            "platform": "facebook",
            "url": target.get("url", ""),
            "uri": target.get("url", ""),
            "cid": "",
            "author_handle": "",
            "author_display_name": target.get("name", "Facebook target"),
            "author_did": "",
            "text": target.get("notes", ""),
            "created_at": "",
            "age_hours": 0,
            "reply_count": 0,
            "repost_count": 0,
            "like_count": 0,
            "quote_count": 0,
            "query": search_query,
            "matched_queries": [search_query],
            "score": round(score, 2),
            "target_search_url": facebook_search_url(search_query),
            "manual_review": True,
        }
        candidate["reason"] = describe_candidate(candidate)
        candidates.append(candidate)

    if not candidates:
        search_query = first_truthy(queries) or topic or "Colorado local culture"
        candidates.append(
            {
                "platform": "facebook",
                "url": facebook_search_url(search_query),
                "uri": facebook_search_url(search_query),
                "cid": "",
                "author_handle": "",
                "author_display_name": "Facebook post search",
                "author_did": "",
                "text": "Manual Facebook review target.",
                "created_at": "",
                "age_hours": 0,
                "reply_count": 0,
                "repost_count": 0,
                "like_count": 0,
                "quote_count": 0,
                "query": search_query,
                "matched_queries": [search_query],
                "score": 1,
                "target_search_url": facebook_search_url(search_query),
                "manual_review": True,
                "reason": "Manual Facebook search target; public post search is not available through the normal Graph API.",
            }
        )

    return sorted(candidates, key=lambda item: (-item["score"], item["author_display_name"]))[:max_candidates]


def load_targets(path=DEFAULT_FACEBOOK_TARGETS_PATH):
    target_path = Path(path)
    if not target_path.exists():
        return DEFAULT_TARGETS
    with target_path.open() as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        return DEFAULT_TARGETS
    return [target for target in payload if isinstance(target, dict) and target.get("url")]


def score_target(target, topic="", query_text=""):
    keywords = " ".join(target.get("keywords") or [])
    notes = target.get("notes") or ""
    haystack = f"{keywords} {notes}"
    score = relevance_points(haystack, f"{topic} {query_text}")
    if "colorado" in haystack.lower() or "denver" in haystack.lower():
        score += 5
    return score


def best_search_query(target, topic, queries):
    local = first_truthy(queries) or f"Colorado {topic}".strip()
    name = target.get("name")
    if name:
        return f"{name} {local}".strip()
    return local


def facebook_search_url(query):
    return f"https://www.facebook.com/search/posts/?q={quote_plus(str(query or '').strip())}"


def describe_candidate(candidate):
    search_url = candidate.get("target_search_url")
    suffix = f" Search link: {search_url}" if search_url else ""
    return (
        f"Curated Facebook review target for `{candidate.get('query')}`. "
        "Choose a specific recent post manually before approving a reply."
        f"{suffix}"
    )


def first_truthy(values):
    for value in values or []:
        if value:
            return value
    return ""
