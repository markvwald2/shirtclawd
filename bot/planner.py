from datetime import date, datetime, timezone

from bot.selector import select_shirts


DEFAULT_PLATFORMS = ("x", "instagram", "facebook", "bluesky")
DEFAULT_DAILY_SPEND_LIMIT_USD = 1.0
DEFAULT_ESTIMATED_INPUT_TOKENS = 1200
DEFAULT_ESTIMATED_OUTPUT_TOKENS = 250


def build_daily_plan(
    inventory,
    history,
    pricing,
    ai_model,
    plan_date=None,
    platforms=DEFAULT_PLATFORMS,
    max_estimated_cost=DEFAULT_DAILY_SPEND_LIMIT_USD,
    approval_required=True,
    expected_input_tokens=DEFAULT_ESTIMATED_INPUT_TOKENS,
    expected_output_tokens=DEFAULT_ESTIMATED_OUTPUT_TOKENS,
):
    normalized_platforms = normalize_platforms(platforms)
    resolved_plan_date = resolve_plan_date(plan_date)
    estimated_ai_cost = estimate_ai_post_cost_usd(
        pricing=pricing,
        model=ai_model,
        expected_input_tokens=expected_input_tokens,
        expected_output_tokens=expected_output_tokens,
    )
    planned_capacity = determine_post_capacity(
        platform_count=len(normalized_platforms),
        max_estimated_cost=max_estimated_cost,
        estimated_ai_cost_per_post=estimated_ai_cost,
    )
    selected = select_shirts(inventory, history, planned_capacity)

    planned_posts = []
    for index, shirt in enumerate(selected):
        planned_posts.append(
            {
                "slot": index + 1,
                "platform": normalized_platforms[index],
                "shirt_id": shirt["shirt_id"],
                "title": shirt["title"],
                "theme": shirt.get("theme", ""),
                "writer_mode": "ai",
                "approval_required": approval_required,
                "approval_status": "pending" if approval_required else "not_required",
                "estimated_ai_cost_usd": estimated_ai_cost,
            }
        )

    estimated_total_cost = None
    if estimated_ai_cost is not None:
        estimated_total_cost = round(estimated_ai_cost * len(planned_posts), 8)

    return {
        "plan_date": resolved_plan_date.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platforms_considered": normalized_platforms,
        "ai_model": ai_model,
        "writer_mode": "ai",
        "approval_required_by_default": approval_required,
        "constraints": {
            "max_estimated_cost_usd": max_estimated_cost,
            "repeat_avoidance": "prefer least recently promoted shirts",
            "fill_schedule": True,
            "allow_platform_skips": True,
        },
        "estimates": {
            "estimated_ai_cost_per_post_usd": estimated_ai_cost,
            "estimated_total_ai_cost_usd": estimated_total_cost,
            "planned_capacity": planned_capacity,
        },
        "planned_posts": planned_posts,
    }


def determine_post_capacity(platform_count, max_estimated_cost, estimated_ai_cost_per_post):
    if platform_count <= 0 or max_estimated_cost <= 0:
        return 0
    if not estimated_ai_cost_per_post or estimated_ai_cost_per_post <= 0:
        return platform_count
    return min(platform_count, int(max_estimated_cost / estimated_ai_cost_per_post))


def estimate_ai_post_cost_usd(pricing, model, expected_input_tokens, expected_output_tokens):
    model_pricing = (pricing or {}).get(model)
    if not model_pricing:
        return None

    input_rate = model_pricing.get("input_per_1m")
    output_rate = model_pricing.get("output_per_1m")
    if input_rate is None or output_rate is None:
        return None

    estimated = (
        (int(expected_input_tokens) / 1_000_000) * float(input_rate)
        + (int(expected_output_tokens) / 1_000_000) * float(output_rate)
    )
    return round(estimated, 8)


def normalize_platforms(platforms):
    ordered = []
    seen = set()
    for platform in platforms:
        normalized = str(platform).strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)
    return ordered


def resolve_plan_date(plan_date):
    if isinstance(plan_date, date):
        return plan_date
    if isinstance(plan_date, str) and plan_date.strip():
        return date.fromisoformat(plan_date)
    return datetime.now(timezone.utc).date()
