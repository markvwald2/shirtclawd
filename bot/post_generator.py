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

def build_ai_post(shirt, components, content_formats, platform, rng):
    platform_post = apply_platform_format(
        platform=platform,
        headline=components["headline"].strip(),
        caption=components["caption"].strip(),
        hashtags=components["hashtags"],
        content_formats=content_formats,
        rng=rng,
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


def apply_platform_format(platform, headline, caption, hashtags, content_formats, rng=None):
    platform_rules = resolve_platform_rules(content_formats, platform)
    headline_prefix = platform_rules.get("headline_prefix", "")
    cta_suffix = choose_cta_suffix(platform_rules.get("cta_suffix", ""), rng=rng)
    cta_separator = str(platform_rules.get("cta_separator", " "))

    formatted_caption = sanitize_caption_for_platform(caption, platform).strip()
    formatted_caption, inline_hashtags = strip_hashtags_from_caption(formatted_caption)
    trimmed_hashtags = normalize_hashtags(list(hashtags or []) + inline_hashtags)[: platform_rules["max_hashtags"]]
    if cta_suffix and not caption_already_contains_cta(formatted_caption, cta_suffix):
        formatted_caption = append_caption_suffix(formatted_caption, cta_suffix, separator=cta_separator)
    if platform_rules.get("append_hashtags_to_caption") and trimmed_hashtags:
        formatted_caption = f"{formatted_caption}\n\n{' '.join(trimmed_hashtags)}"

    return {
        "headline": f"{headline_prefix}{headline}",
        "caption": formatted_caption,
        "hashtags": trimmed_hashtags,
    }


def sanitize_caption_for_platform(caption, platform):
    text = str(caption or "").strip()
    if platform in {"instagram", "bluesky"}:
        text = strip_urls(text)
    if platform == "instagram":
        text = dedupe_instagram_boilerplate(text)
    return normalize_caption_whitespace(text)


def choose_cta_suffix(cta_value, rng=None):
    if isinstance(cta_value, list):
        options = [str(item).strip() for item in cta_value if str(item).strip()]
        if not options:
            return ""
        chooser = rng if rng is not None else random
        return chooser.choice(options)
    return str(cta_value or "").strip()


def caption_already_contains_cta(caption, cta_suffix):
    caption_words = normalize_for_cta_match(caption)
    cta_words = normalize_for_cta_match(cta_suffix)
    if not caption_words or not cta_words:
        return False
    if "link in bio" in caption_words and "link in bio" in cta_words:
        return True
    return cta_words in caption_words


def append_caption_suffix(caption, suffix, separator=" "):
    base = str(caption or "").strip()
    text = str(suffix or "").strip()
    if not text:
        return base
    if not base:
        return text
    return f"{base}{separator}{text}".strip()


def normalize_for_cta_match(text):
    return " ".join(re.findall(r"[a-z0-9]+", str(text or "").lower()))


def strip_hashtags_from_caption(text):
    inline_hashtags = re.findall(r"(?<!\w)#[A-Za-z0-9_]+", str(text or ""))
    without_hashtags = re.sub(r"(?<!\w)#[A-Za-z0-9_]+\b", "", str(text or ""))
    return normalize_caption_whitespace(without_hashtags), inline_hashtags


def strip_urls(text):
    without_urls = re.sub(r"https?://\S+", "", str(text or ""), flags=re.IGNORECASE)
    return without_urls


def dedupe_instagram_boilerplate(text):
    value = str(text or "")
    if value.lower().count("link in bio") <= 1:
        return value

    seen_link_in_bio = False

    def replace_match(match):
        nonlocal seen_link_in_bio
        if not seen_link_in_bio:
            seen_link_in_bio = True
            return match.group(0)
        return ""

    return re.sub(r"(?i)\blink in bio\b[.!]?", replace_match, value)


def normalize_caption_whitespace(text):
    collapsed = re.sub(r"[ \t]+", " ", str(text or ""))
    collapsed = re.sub(r" *\n *", "\n", collapsed)
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
    return collapsed.strip()


def resolve_platform_rules(content_formats, platform):
    rules = dict(content_formats["default"])
    rules.update(content_formats.get(platform, {}))
    return rules


def build_alt_text(shirt):
    topic = shirt.get("theme") or "graphic"
    return f"Product image for the {shirt['title']} shirt featuring a {topic} theme."


def random_source(seed):
    return random.Random(seed)
