import json
import os
import random
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OPENAI_API_URL = "https://api.openai.com/v1/responses"
DEFAULT_AI_MODEL = "gpt-4o-mini"
DEFAULT_BRAND_VOICE = (
    "Dry, sharp, niche, and slightly irreverent. Favor wit over friendliness and "
    "specificity over hype. Never sound corporate, wholesome, or generic."
)
TONE_PRESETS = {
    "deadpan": (
        "Dry, understated, and slightly smug. Deliver the joke without begging for attention. "
        "Assume the audience is smart enough to catch up. Avoid cheerful promo language and overexplaining."
    ),
    "edgy_snarky": (
        "Dry, sharp, irreverent, and a little smug. Write for people who enjoy niche references "
        "and jokes with some bite. Keep it clever, not cheerful. Slight snark is good; forced "
        "edginess, generic hype, and overexplaining are not."
    ),
    "reference_nerd": (
        "Culturally literate, specific, and quietly confident. Write like the fun is in recognizing "
        "the reference. Reward insider knowledge without sounding gatekeepy or academic."
    ),
    "barstool_smart": (
        "Wry, skeptical, and casually cutting. Sound like someone making a smart joke over drinks, "
        "not performing stand-up. Keep the punch precise. Avoid ranting, preachiness, or frat-boy energy."
    ),
    "fan_insider": (
        "Confident and specific, aimed at people who already picked a side. Let the reference or "
        "fandom do the work. Avoid broad, beginner-level explanation and generic crowd-pleasing language."
    ),
    "dry_aggressive": (
        "Blunt, clever, and mildly antagonistic in a controlled way. The copy can have teeth, but "
        "it should still sound intentional and smart. Avoid sounding angry, crass, or desperate to shock."
    ),
}
THEME_TONE_GUIDANCE = {
    "religion": "Irreverence is allowed when the joke already has some bite, but keep it witty rather than preachy.",
    "funny": "Keep the joke dry and a little mean if it helps, but avoid novelty-gift-shop energy.",
    "movies": "Write like a knowing reference flex, not a plot summary.",
    "sports": "Trash talk and rivalry energy are fine when they feel specific and earned.",
}
TONE_EXAMPLES = {
    "edgy_snarky": [
        {
            "headline": "Science gets the last call",
            "caption": (
                "For people who trust fermentation more than fake wisdom. The joke lands harder when "
                "it sounds amused instead of impressed."
            ),
        },
        {
            "headline": "A nice little insult disguised as a shirt",
            "caption": (
                "Keep the copy dry, specific, and just smug enough to make the right audience grin."
            ),
        },
    ],
    "barstool_smart": [
        {
            "headline": "Too informed to be wholesome",
            "caption": (
                "Aim for skeptical, conversational snark. It should sound like a sharp aside, not a rant."
            ),
        }
    ],
}
STYLE_VARIATION_HINTS = [
    "Use a different opening move than generic merch copy. Avoid defaulting to 'Because...' or 'Ever wanted...' unless it is genuinely strongest.",
    "Vary sentence rhythm and structure. Avoid sounding like the same template with new nouns swapped in.",
    "Lean into one sharp angle rather than stacking multiple weak ones. Distinctiveness matters more than completeness.",
    "Let the reference or joke land in a fresh way. Avoid repeating the same cadence you might use for another shirt in this batch.",
]


class AIWriterError(RuntimeError):
    pass


def generate_post_components(
    shirt,
    platform,
    api_key=None,
    model=DEFAULT_AI_MODEL,
    timeout=45,
    recent_posts=None,
    post_context=None,
):
    resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not resolved_api_key:
        raise AIWriterError("OPENAI_API_KEY is not set.")

    prompt = build_user_prompt(shirt, platform, recent_posts=recent_posts, post_context=post_context)
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "You are writing one social post for a t-shirt brand with a dry, sharp, irreverent voice. "
                    "Return JSON only. Choose the most effective post angle for the shirt, "
                    "write custom copy, and keep the tone specific rather than generic. "
                    "Avoid wholesome promo cliches, generic merch hype, and corporate brand language."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "shirt_post",
                "description": "Structured social post output for a single t-shirt listing.",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "headline": {"type": "string"},
                        "caption": {"type": "string"},
                        "hashtags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "maxItems": 6
                        },
                        "alt_text": {"type": "string"},
                        "post_type": {"type": "string"}
                    },
                    "required": ["headline", "caption", "hashtags", "alt_text", "post_type"]
                }
            }
        }
    }

    request = Request(
        OPENAI_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {resolved_api_key}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            raw_response = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise AIWriterError(f"OpenAI API request failed: {exc.code} {error_body}") from exc
    except URLError as exc:
        raise AIWriterError(f"OpenAI API request failed: {exc}") from exc

    return parse_response(raw_response)


def build_user_prompt(shirt, platform, recent_posts=None, post_context=None):
    tone = str(shirt.get("tone", "")).strip()
    theme = str(shirt.get("theme", "")).strip()
    variation_hint = random.choice(STYLE_VARIATION_HINTS)
    platform_url_guidance = {
        "instagram": (
            "Do not include a raw URL in the caption. Avoid stock CTA wording. "
            "If a call to action helps, vary the phrasing and do not repeat 'link in bio'."
        ),
        "bluesky": "Do not rely on a pasted raw URL in the caption. Write clean copy; the publisher will attach the destination separately.",
    }
    repetition_guidance = build_repetition_guidance(platform, recent_posts or [])
    normalized_context = normalize_post_context(post_context)
    content_guidance = build_content_goal_guidance(normalized_context)
    return json.dumps(
        {
            "task": "Generate one JSON social post.",
            "platform": platform,
            "brand_voice": DEFAULT_BRAND_VOICE,
            "variation_hint": variation_hint,
            "theme_tone_guidance": THEME_TONE_GUIDANCE.get(theme, ""),
            "tone_preset": {
                "name": tone,
                "guidance": TONE_PRESETS.get(tone, ""),
            },
            "tone_examples": TONE_EXAMPLES.get(tone, []),
            "shirt": {
                "shirt_id": shirt["shirt_id"],
                "title": shirt["title"],
                "theme": theme,
                "sub_theme": shirt.get("sub_theme", ""),
                "tags": shirt.get("tags", []),
                "url": shirt["url"],
                "image_url": shirt["image_url"],
                "description": shirt.get("description", ""),
                "reference_summary": shirt.get("reference_summary", ""),
                "target_audience": shirt.get("target_audience", []),
                "tone": tone,
                "tone_notes": shirt.get("tone_notes", ""),
                "notes": shirt.get("notes", ""),
            },
            "post_context": normalized_context,
            "requirements": [
                "Pick the most effective angle for this specific shirt.",
                "Write a custom headline and caption, not a template.",
                "Keep hashtags relevant and concise.",
                "Use the reference summary and target audience when they are provided.",
                "Use the brand voice, theme tone guidance, tone preset, and tone notes when they are provided.",
                "Honor the variation hint so the writing does not feel repetitive from post to post.",
                "Favor dry specificity over cheerful sales copy.",
                content_guidance,
                platform_url_guidance.get(platform, "Include the product URL in the caption."),
                repetition_guidance,
                "Return JSON only."
            ]
        }
    )


def normalize_post_context(post_context):
    if not isinstance(post_context, dict):
        return {}

    keys = (
        "campaign",
        "series",
        "audience_lane",
        "content_goal",
        "content_format",
        "cta_goal",
        "campaign_prompt_guidance",
        "campaign_strategy_note",
        "active_offer",
        "discount_percent",
        "offer_scope",
        "offer_ends_on",
        "secondary_offer",
    )
    return {
        key: str(post_context.get(key, "")).strip()
        for key in keys
        if str(post_context.get(key, "")).strip()
    }


def build_content_goal_guidance(post_context):
    content_goal = post_context.get("content_goal", "")
    cta_goal = post_context.get("cta_goal", "")
    campaign_guidance = post_context.get("campaign_prompt_guidance", "")
    strategy_note = post_context.get("campaign_strategy_note", "")

    goal_guidance = {
        "conversation": (
            "This is top-of-funnel conversation content. Do not lead with a purchase ask. "
            "Create replies, shares, or playful disagreement before mentioning the shirt."
        ),
        "product_connected": (
            "This is middle-of-funnel series content. Tie the joke to the shirt or campaign, "
            "but keep the post useful as entertainment even if nobody clicks."
        ),
        "direct_offer": (
            "This is conversion content. A purchase CTA is allowed, but keep it specific, dry, "
            "and native to the joke instead of generic merch copy."
        ),
    }.get(content_goal, "Match the requested content goal when one is provided.")

    cta_guidance = {
        "reply": "End with a specific reply prompt, not a vague engagement question.",
        "share": "Make the post easy to send to a friend or local page without asking too hard.",
        "vote": "Ask people to vote, nominate, or choose the next target in the series.",
        "buy": "Use a clear but non-desperate purchase prompt if it fits the platform.",
    }.get(cta_goal, "")

    parts = [goal_guidance]
    if cta_guidance:
        parts.append(cta_guidance)
    if campaign_guidance:
        parts.append(campaign_guidance)
    if strategy_note:
        parts.append(strategy_note)
    offer_guidance = build_offer_guidance(post_context)
    if offer_guidance:
        parts.append(offer_guidance)
    return " ".join(parts)


def build_offer_guidance(post_context):
    active_offer = post_context.get("active_offer", "")
    if not active_offer:
        return ""

    ends_on = post_context.get("offer_ends_on", "")
    secondary_offer = post_context.get("secondary_offer", "")
    content_goal = post_context.get("content_goal", "")
    cta_goal = post_context.get("cta_goal", "")
    expiration = f" through {ends_on}" if ends_on else ""
    secondary = f" A secondary storewide offer is {secondary_offer}." if secondary_offer else ""
    if content_goal == "direct_offer" or cta_goal == "buy":
        return (
            f"The current offer is {active_offer}{expiration}. Mention it clearly if this post asks "
            f"for the sale, while keeping the voice dry and non-desperate.{secondary}"
        )
    return (
        f"The current offer is {active_offer}{expiration}, but do not force it into this post unless "
        f"it supports the assigned content goal without turning the post into an ad.{secondary}"
    )


def parse_response(raw_response):
    payload = json.loads(raw_response)
    if payload.get("error"):
        raise AIWriterError(f"OpenAI API error: {payload['error']}")

    text = payload.get("output_text")
    if not text:
        text = extract_text_from_output(payload.get("output", []))
    if not text:
        raise AIWriterError("OpenAI response did not contain text output.")

    try:
        components = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIWriterError(f"OpenAI response was not valid JSON: {exc}") from exc

    validate_components(components)
    return {
        "components": components,
        "usage": payload.get("usage", {}),
        "response_id": payload.get("id"),
    }


def extract_text_from_output(output):
    chunks = []
    for item in output:
        for content in item.get("content", []):
            text_value = content.get("text")
            if isinstance(text_value, str) and text_value.strip():
                chunks.append(text_value)
    return "\n".join(chunks).strip()


def validate_components(parsed):
    required = ("headline", "caption", "hashtags", "alt_text", "post_type")
    for key in required:
        value = parsed.get(key)
        if key == "hashtags":
            if not isinstance(value, list) or not value:
                raise AIWriterError("OpenAI response hashtags field was missing or invalid.")
            continue
        if not isinstance(value, str) or not value.strip():
            raise AIWriterError(f"OpenAI response field {key} was missing or invalid.")


def build_repetition_guidance(platform, recent_posts):
    if not recent_posts:
        return "Avoid repeated CTA phrases and duplicate hashtag blocks."

    recent_ctas = []
    recent_hashtag_combos = []
    for post in recent_posts[:5]:
        caption = str(post.get("caption", "")).strip()
        hashtags = [str(tag).strip() for tag in post.get("hashtags", []) if str(tag).strip()]
        if caption:
            recent_ctas.append(summarize_recent_post(caption))
        if hashtags:
            recent_hashtag_combos.append(hashtags)

    message = [
        "Avoid repeating CTA phrases or hashtag sets from these recent posts."
    ]
    if platform == "instagram":
        message.append("Do not use 'link in bio' more than once, and prefer a fresh CTA when possible.")
    if recent_ctas:
        message.append(f"Recent caption examples to avoid echoing: {recent_ctas[:3]}.")
    if recent_hashtag_combos:
        message.append(f"Recent hashtag combos to avoid repeating exactly: {recent_hashtag_combos[:3]}.")
    return " ".join(message)


def summarize_recent_post(text):
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    return cleaned[:180]
