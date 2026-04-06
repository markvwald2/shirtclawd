from dataclasses import dataclass
import re
from typing import Optional


SUPPORTED_PLATFORMS = ("instagram", "facebook", "x", "bluesky", "reels", "tiktok")
GENERATION_VERBS = ("write", "generate", "create", "make", "draft")


@dataclass(frozen=True)
class ParsedCommand:
    action: str
    platform: str
    count: int
    query: Optional[str] = None
    original_text: str = ""


def parse_command(text):
    original_text = str(text or "").strip()
    if not original_text:
        raise ValueError("Command text cannot be empty.")

    normalized = normalize_text(original_text)
    action = parse_action(normalized)
    if action != "generate":
        raise ValueError("Only generation commands are supported right now.")

    platform = parse_platform(normalized)
    count = parse_count(normalized)
    query = parse_query(normalized, platform)

    return ParsedCommand(
        action=action,
        platform=platform,
        count=count,
        query=query,
        original_text=original_text,
    )


def normalize_text(text):
    return re.sub(r"\s+", " ", text.strip().lower())


def parse_action(text):
    if any(re.search(rf"\b{verb}\b", text) for verb in GENERATION_VERBS):
        return "generate"
    raise ValueError("Couldn't tell what action you want. Try 'write 2 posts for Instagram'.")


def parse_platform(text):
    for platform in SUPPORTED_PLATFORMS:
        if re.search(rf"\b{re.escape(platform)}\b", text):
            return platform
    raise ValueError(f"Couldn't find a supported platform in: {', '.join(SUPPORTED_PLATFORMS)}")


def parse_count(text):
    match = re.search(r"\b(\d+)\s+posts?\b", text)
    if match:
        return max(1, int(match.group(1)))

    if re.search(r"\b(an?|one)\s+posts?\b", text):
        return 1

    return 1


def parse_query(text, platform):
    platform_match = re.search(rf"\bfor\s+{re.escape(platform)}\b", text)
    if not platform_match:
        return None

    remainder = text[platform_match.end():].strip(" ,.")
    if not remainder:
        return None

    if remainder.startswith("for "):
        remainder = remainder[4:]
    elif remainder.startswith("about "):
        remainder = remainder[6:]

    remainder = re.sub(r"^(the|our)\s+", "", remainder).strip()
    remainder = re.sub(r"\s+(please|today|now)$", "", remainder).strip()
    return remainder or None
