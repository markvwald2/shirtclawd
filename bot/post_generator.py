import json
import random
import re
from pathlib import Path


DEFAULT_CONTENT_FORMATS_PATH = Path("config/content_formats.json")
DEFAULT_THEME_FORMATS_PATH = Path("config/theme_formats.json")


def load_content_formats(path=DEFAULT_CONTENT_FORMATS_PATH):
    with Path(path).open() as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict) or "default" not in payload:
        raise ValueError("Content formats config must be a JSON object with a default section.")

    return payload


def load_theme_formats(path=DEFAULT_THEME_FORMATS_PATH):
    with Path(path).open() as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict) or "default" not in payload:
        raise ValueError("Theme formats config must be a JSON object with a default section.")

    return payload


def build_posts(shirts, theme_formats, content_formats, platform, rng):
    posts = []
    for shirt in shirts:
        posts.append(build_rule_based_post(shirt, theme_formats, content_formats, platform, rng))
    return posts


def build_rule_based_post(shirt, theme_formats, content_formats, platform, rng):
    topic = (shirt.get("theme") or "graphic tees").replace("-", " ")
    strategy = decide_strategy(shirt, theme_formats, rng)
    headline = build_headline(shirt, strategy, rng)
    caption = build_caption(shirt, strategy, theme_formats)
    tags = build_hashtags(shirt)
    platform_post = apply_platform_format(
        platform=platform,
        headline=headline,
        caption=caption,
        hashtags=tags,
        content_formats=content_formats,
    )

    return {
        "shirt_id": shirt["shirt_id"],
        "title": shirt["title"],
        "headline": platform_post["headline"],
        "caption": platform_post["caption"],
        "hashtags": platform_post["hashtags"],
        "alt_text": build_alt_text(shirt),
        "image_url": shirt["image_url"],
        "url": shirt["url"],
        "post_type": strategy,
        "theme": topic,
        "priority": rng.randint(1, 3),
        "platform": platform,
        "writer_mode": "rule",
    }


def build_ai_post(shirt, components, content_formats, platform, rng):
    platform_post = apply_platform_format(
        platform=platform,
        headline=components["headline"].strip(),
        caption=components["caption"].strip(),
        hashtags=components["hashtags"],
        content_formats=content_formats,
    )
    topic = (shirt.get("theme") or "graphic tees").replace("-", " ")
    return {
        "shirt_id": shirt["shirt_id"],
        "title": shirt["title"],
        "headline": platform_post["headline"],
        "caption": platform_post["caption"],
        "hashtags": platform_post["hashtags"],
        "alt_text": components["alt_text"].strip(),
        "image_url": shirt["image_url"],
        "url": shirt["url"],
        "post_type": normalize_post_type(components.get("post_type"), platform),
        "theme": topic,
        "priority": rng.randint(1, 3),
        "platform": platform,
        "writer_mode": "ai",
    }


def build_hashtags(shirt):
    base_tags = ["#thirdstringshirts", "#funnyshirts"]
    tag_tags = [f"#{tag.replace(' ', '').replace('-', '')}" for tag in shirt.get("tags", [])[:3]]
    return normalize_hashtags(base_tags + tag_tags)


def normalize_hashtags(hashtags):
    combined = []
    seen = set()
    for tag in hashtags:
        text = clean_hashtag(tag)
        if not text:
            continue
        normalized = text.lower()
        display = text
        if normalized not in seen:
            seen.add(normalized)
            combined.append(display)
    return combined


def clean_hashtag(tag):
    text = str(tag).strip()
    if not text:
        return ""

    text = text.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "").replace("\ufeff", "")
    text = text.replace("#@", "#").replace("@", "")
    if not text.startswith("#"):
        text = f"#{text}"

    body = re.sub(r"[^A-Za-z0-9_]+", "", text.lstrip("#"))
    if not body:
        return ""
    return f"#{body}"


def normalize_post_type(post_type, platform):
    text = str(post_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not text or text in {platform, "social_post", "post", "default"}:
        return "ai_custom"
    return text


def apply_platform_format(platform, headline, caption, hashtags, content_formats):
    platform_rules = resolve_platform_rules(content_formats, platform)
    trimmed_hashtags = normalize_hashtags(hashtags)[: platform_rules["max_hashtags"]]
    headline_prefix = platform_rules.get("headline_prefix", "")
    cta_suffix = platform_rules.get("cta_suffix", "").strip()

    formatted_caption = caption
    if cta_suffix:
        formatted_caption = f"{formatted_caption} {cta_suffix}"
    if platform_rules.get("append_hashtags_to_caption") and trimmed_hashtags:
        formatted_caption = f"{formatted_caption}\n\n{' '.join(trimmed_hashtags)}"

    return {
        "headline": f"{headline_prefix}{headline}",
        "caption": formatted_caption,
        "hashtags": trimmed_hashtags,
    }


def resolve_platform_rules(content_formats, platform):
    rules = dict(content_formats["default"])
    rules.update(content_formats.get(platform, {}))
    return rules


def build_alt_text(shirt):
    topic = shirt.get("theme") or "graphic"
    return f"Product image for the {shirt['title']} shirt featuring a {topic} theme."


def decide_strategy(shirt, theme_formats, rng):
    theme = shirt.get("theme") or "default"
    config = theme_formats.get(theme, theme_formats["default"])
    allowed_angles = config.get("angles", theme_formats["default"]["angles"])
    scores = {}
    for angle in allowed_angles:
        scores[angle] = strategy_score(angle, shirt)

    highest = max(scores.values()) if scores else 0
    best_angles = [angle for angle, score in scores.items() if score == highest]
    return rng.choice(best_angles or theme_formats["default"]["angles"])


def strategy_score(angle, shirt):
    theme = (shirt.get("theme") or "").lower()
    sub_theme = (shirt.get("sub_theme") or "").lower()
    title = shirt["title"].lower()
    tags = [tag.lower() for tag in shirt.get("tags", [])]

    if angle == "local_pride":
        return int(theme == "geography") + int("," in shirt["title"]) + int("state" in sub_theme)
    if angle == "insider_nod":
        return int(theme == "transportation") + int("cta" in sub_theme or "cta" in tags) + int("line" in title)
    if angle == "reference_flex":
        return int(theme in {"movies", "music", "religion", "tv"}) + int(bool(sub_theme)) + int(len(tags) <= 2)
    if angle == "fan_identity":
        return int(theme == "sports") + int("sports" in tags) + int(bool(sub_theme))
    if angle == "debate":
        return int(theme in {"sports", "movies"}) + int(bool(sub_theme))
    if angle == "deadpan":
        return int(theme == "funny") + int("satire" in tags) + int(len(title.split()) <= 5)
    if angle == "collector":
        return int("state-flags" in tags or "state-capitals" in tags) + int(bool(sub_theme))
    if angle == "curiosity":
        return int(not sub_theme) + int(len(tags) <= 2)
    if angle == "spotlight":
        return 1
    return 0


def build_headline(shirt, strategy, rng):
    title = shirt["title"]
    reference_anchor = build_reference_anchor(shirt)
    options = {
        "local_pride": [
            f"{title} is for the people who get it",
            f"A deep-cut geography pick: {title}",
        ],
        "insider_nod": [
            f"{title} rewards transit brain",
            f"{title} is an inside joke with a fare card",
        ],
        "reference_flex": [
            f"{title} is a reference worth keeping",
            f"{title} lands if {reference_anchor} already means something to you",
        ],
        "fan_identity": [
            f"{title} wears the fandom plainly",
            f"{title} is built for committed fans",
        ],
        "debate": [
            f"{title} could start an argument",
            f"{title} is not neutral territory",
        ],
        "deadpan": [
            f"{title} says it without trying too hard",
            f"{title} keeps the joke dry",
        ],
        "collector": [
            f"{title} belongs in the rotation",
            f"{title} is one for the niche collection",
        ],
        "curiosity": [
            f"{title} earns a second look",
            f"{title} is weirdly specific in the right way",
        ],
        "spotlight": [
            f"{title} is up today",
            f"Current ClawdBot pick: {title}",
        ],
    }
    return rng.choice(options.get(strategy, options["spotlight"]))


def build_caption(shirt, strategy, theme_formats):
    title = shirt["title"]
    theme = (shirt.get("theme") or "graphic tees").replace("-", " ")
    sub_theme = (shirt.get("sub_theme") or "").replace("-", " ")
    url = shirt["url"]
    audience = resolve_audience(shirt, theme_formats)
    hook = build_hook(shirt)
    reference_anchor = build_reference_anchor(shirt)
    detail = build_detail(shirt)

    if strategy == "local_pride":
        opener = f"{title} is the kind of shirt that only works because someone out there genuinely cares about {sub_theme or theme}."
        closer = f"It is a clean pick for {audience}. {url}"
    elif strategy == "insider_nod":
        opener = f"{title} is aimed at the people who notice route maps, station names, and the tiny details everyone else walks past."
        closer = f"If {sub_theme or hook} already means something to you, this post probably did its job. {url}"
    elif strategy == "reference_flex":
        opener = f"{title} works best when the reference lands immediately and needs no explanation."
        closer = f"It is a strong fit for {audience}, especially if {reference_anchor} is already familiar. {url}"
    elif strategy == "fan_identity":
        opener = f"{title} leans into {theme} without pretending to be for casual observers."
        closer = f"This one is better for people who already picked a side. {url}"
    elif strategy == "debate":
        opener = f"{title} has the right energy for a post that invites opinions instead of just asking for a click."
        closer = f"There is enough specificity here to make the comments do the rest. {url}"
    elif strategy == "deadpan":
        opener = f"{title} works because it delivers the joke straight and leaves the audience to catch up."
        closer = f"It fits {audience} and does not need extra decoration. {url}"
    elif strategy == "collector":
        opener = f"{title} feels like part of a larger set, which makes it useful when the goal is showing range without losing the niche."
        closer = f"{detail} {url}"
    elif strategy == "curiosity":
        opener = f"{title} is specific enough to stop the scroll even before the joke fully registers."
        closer = f"It is the kind of design that rewards curiosity and a slightly strange sense of humor. {url}"
    else:
        opener = f"{title} is today's pick from the {theme} side of the catalog."
        closer = f"{detail} {url}"

    return f"{opener} {detail} {closer}"


def build_hook(shirt):
    theme = str(shirt.get("theme") or "").strip().lower()
    for candidate in [shirt.get("sub_theme"), *(shirt.get("tags") or [])]:
        if candidate is None:
            continue
        text = str(candidate).strip().replace("-", " ")
        if text:
            return text.lower()
    return theme or "offbeat humor"


def build_reference_anchor(shirt):
    reference_summary = str(shirt.get("reference_summary") or "").strip()
    if reference_summary:
        return reference_summary

    sub_theme = str(shirt.get("sub_theme") or "").strip().replace("-", " ")
    if sub_theme:
        return sub_theme

    theme = str(shirt.get("theme") or "").strip().lower()
    for tag in shirt.get("tags", []):
        normalized = str(tag).strip().replace("-", " ").lower()
        if normalized and normalized != theme:
            return normalized

    return "the premise"


def build_detail(shirt):
    reference_summary = str(shirt.get("reference_summary") or "").strip()
    if reference_summary:
        return reference_summary

    if shirt.get("sub_theme"):
        return f"The reference point here is {shirt['sub_theme']}."
    if shirt.get("tags"):
        tag_text = ", ".join(tag.replace("-", " ") for tag in shirt["tags"][:3])
        return f"It pulls from {tag_text}."
    return "It leans on a very specific joke."


def resolve_audience(shirt, theme_formats):
    target_audience = shirt.get("target_audience") or []
    if target_audience:
        return ", ".join(item.replace("-", " ") for item in target_audience[:3])

    return theme_formats.get(shirt.get("theme"), theme_formats["default"]).get(
        "audience",
        theme_formats["default"]["audience"],
    )


def random_source(seed):
    return random.Random(seed)
