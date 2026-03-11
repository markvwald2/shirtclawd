import json
import os
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


class AIWriterError(RuntimeError):
    pass


def generate_post_components(shirt, platform, api_key=None, model=DEFAULT_AI_MODEL, timeout=45):
    resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not resolved_api_key:
        raise AIWriterError("OPENAI_API_KEY is not set.")

    prompt = build_user_prompt(shirt, platform)
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


def build_user_prompt(shirt, platform):
    tone = str(shirt.get("tone", "")).strip()
    theme = str(shirt.get("theme", "")).strip()
    return json.dumps(
        {
            "task": "Generate one JSON social post.",
            "platform": platform,
            "brand_voice": DEFAULT_BRAND_VOICE,
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
            "requirements": [
                "Pick the most effective angle for this specific shirt.",
                "Write a custom headline and caption, not a template.",
                "Keep hashtags relevant and concise.",
                "Use the reference summary and target audience when they are provided.",
                "Use the brand voice, theme tone guidance, tone preset, and tone notes when they are provided.",
                "Favor dry specificity over cheerful sales copy.",
                "Include the product URL in the caption.",
                "Return JSON only."
            ]
        }
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
