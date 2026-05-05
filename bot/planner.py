from datetime import date, datetime, timezone

from bot.campaigns import apply_campaign_metadata, apply_campaign_set_metadata, resolve_campaign
from bot.selector import select_matching_shirts, select_shirts


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
    campaign=None,
    include_campaign_set_post=False,
    campaign_set_platform=None,
    campaign_set_platforms=None,
    campaign_set_size=4,
):
    normalized_platforms = normalize_platforms(platforms)
    campaign_definition = resolve_campaign(campaign)
    resolved_plan_date = resolve_plan_date(plan_date)
    set_platforms = resolve_campaign_set_platforms(
        normalized_platforms,
        campaign_set_platform=campaign_set_platform,
        campaign_set_platforms=campaign_set_platforms,
    )
    estimated_ai_cost = estimate_ai_post_cost_usd(
        pricing=pricing,
        model=ai_model,
        expected_input_tokens=expected_input_tokens,
        expected_output_tokens=expected_output_tokens,
    )
    set_post_requested = bool(include_campaign_set_post and campaign_definition and set_platforms)
    requested_post_count = len(normalized_platforms) + (len(set_platforms) if set_post_requested else 0)
    planned_capacity = determine_post_capacity(
        platform_count=requested_post_count,
        max_estimated_cost=max_estimated_cost,
        estimated_ai_cost_per_post=estimated_ai_cost,
    )
    individual_capacity = min(len(normalized_platforms), planned_capacity)
    set_post_capacity = max(planned_capacity - individual_capacity, 0)
    active_set_platforms = set_platforms[:set_post_capacity] if set_post_requested else []
    include_set_post = bool(active_set_platforms)
    set_size = max(int(campaign_set_size or 0), 0)
    selection_count = max(individual_capacity, set_size if include_set_post else 0)
    if campaign_definition:
        selected = select_matching_shirts(
            inventory,
            history,
            selection_count,
            campaign_definition["query"],
        )
    else:
        selected = select_shirts(inventory, history, selection_count)

    planned_posts = []
    for index, shirt in enumerate(selected[:individual_capacity]):
        plan_entry = {
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
        planned_posts.append(apply_campaign_metadata(plan_entry, campaign_definition, index))

    if include_set_post:
        set_shirts = selected[:set_size]
        if len(set_shirts) >= 2:
            set_definition = campaign_definition.get("set_post") or {}
            for platform in active_set_platforms:
                set_entry = {
                    "slot": len(planned_posts) + 1,
                    "platform": platform,
                    "shirt_id": f"{campaign_definition['campaign']}_set",
                    "shirt_ids": [shirt["shirt_id"] for shirt in set_shirts],
                    "title": set_definition.get("title", campaign_definition["series"]),
                    "titles": [shirt["title"] for shirt in set_shirts],
                    "theme": set_definition.get("theme", campaign_definition["series"]),
                    "writer_mode": "ai",
                    "post_kind": "series_set",
                    "approval_required": approval_required,
                    "approval_status": "pending" if approval_required else "not_required",
                    "estimated_ai_cost_usd": estimated_ai_cost,
                    "collection_size": len(set_shirts),
                    "collection_items": [
                        {"shirt_id": shirt["shirt_id"], "title": shirt["title"]}
                        for shirt in set_shirts
                    ],
                }
                planned_posts.append(apply_campaign_set_metadata(set_entry, campaign_definition))

    estimated_total_cost = None
    if estimated_ai_cost is not None:
        estimated_total_cost = round(estimated_ai_cost * len(planned_posts), 8)

    return {
        "plan_date": resolved_plan_date.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platforms_considered": normalized_platforms,
        "ai_model": ai_model,
        "writer_mode": "ai",
        "campaign": campaign_definition["campaign"] if campaign_definition else None,
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
        normalized = normalize_platform(platform)
        if normalized and normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)
    return ordered


def normalize_platform(platform):
    return str(platform or "").strip().lower()


def resolve_campaign_set_platforms(normalized_platforms, campaign_set_platform=None, campaign_set_platforms=None):
    requested = []
    if campaign_set_platforms:
        requested.extend(campaign_set_platforms)
    if campaign_set_platform:
        requested.append(campaign_set_platform)
    if not requested:
        requested = list(normalized_platforms)

    resolved = []
    seen = set()
    for platform in requested:
        normalized = normalize_platform(platform)
        if normalized == "all":
            for candidate in normalized_platforms:
                if candidate not in seen:
                    seen.add(candidate)
                    resolved.append(candidate)
            continue
        if normalized and normalized not in seen:
            seen.add(normalized)
            resolved.append(normalized)
    return resolved


def resolve_plan_date(plan_date):
    if isinstance(plan_date, date):
        return plan_date
    if isinstance(plan_date, str) and plan_date.strip():
        return date.fromisoformat(plan_date)
    return datetime.now(timezone.utc).date()
