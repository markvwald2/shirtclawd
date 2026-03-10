import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OPENAI_API_URL = "https://api.openai.com/v1/responses"
DEFAULT_AI_MODEL = "gpt-4o-mini"


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
                    "You are writing one social post for a t-shirt brand. "
                    "Return JSON only. Choose the most effective post angle for the shirt, "
                    "write custom copy, and keep the tone specific rather than generic."
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
    return json.dumps(
        {
            "task": "Generate one JSON social post.",
            "platform": platform,
            "shirt": {
                "shirt_id": shirt["shirt_id"],
                "title": shirt["title"],
                "theme": shirt.get("theme", ""),
                "sub_theme": shirt.get("sub_theme", ""),
                "tags": shirt.get("tags", []),
                "url": shirt["url"],
                "image_url": shirt["image_url"],
                "description": shirt.get("description", "")
            },
            "requirements": [
                "Pick the most effective angle for this specific shirt.",
                "Write a custom headline and caption, not a template.",
                "Keep hashtags relevant and concise.",
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
