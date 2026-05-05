CAMPAIGNS = {
    "coloradans_against": {
        "campaign": "coloradans_against",
        "series": "Coloradans Against",
        "audience_lane": "colorado_regional_sarcasm",
        "query": "coloradans against shirts",
        "strategy_note": (
            "Lead with local argument starters and recognizable Colorado anti-cliche jokes. "
            "Entertain first; sell only when the content goal calls for it."
        ),
        "active_offer": {
            "description": "20% off all Spreadshirt orders",
            "discount_percent": 20,
            "scope": "all Spreadshirt orders",
            "starts_on": "2026-05-15",
            "ends_on": "2026-05-19",
        },
        "set_post": {
            "title": "Coloradans Against Shirt Line",
            "theme": "Coloradans Against",
            "content_goal": "product_connected",
            "content_format": "series_set",
            "cta_goal": "buy",
            "prompt_guidance": (
                "This is a multi-image carousel/set post. Write about the Coloradans Against "
                "line as a whole, not one shirt. Invite people to swipe through the lineup and "
                "keep the Colorado-local argument energy."
            ),
        },
        "content_sequence": [
            {
                "content_goal": "conversation",
                "content_format": "group_chat_argument",
                "cta_goal": "reply",
                "prompt_guidance": (
                    "Make this a Colorado culture argument starter. Do not ask for a purchase. "
                    "Invite a specific reply, ranking, vote, or playful disagreement."
                ),
            },
            {
                "content_goal": "conversation",
                "content_format": "pick_your_enemy",
                "cta_goal": "share",
                "prompt_guidance": (
                    "Make this easy to send to a Colorado friend who has strong opinions. "
                    "Keep the product secondary and the local joke primary."
                ),
            },
            {
                "content_goal": "product_connected",
                "content_format": "series_spotlight",
                "cta_goal": "vote",
                "prompt_guidance": (
                    "Connect the shirt to the larger Coloradans Against series. "
                    "Invite people to nominate or vote on the next sacred cow."
                ),
            },
            {
                "content_goal": "direct_offer",
                "content_format": "soft_purchase",
                "cta_goal": "buy",
                "prompt_guidance": (
                    "This can ask for the sale, but keep it dry and local. "
                    "Avoid sounding like a generic merch ad."
                ),
            },
        ],
    }
}


def resolve_campaign(campaign):
    key = normalize_campaign_key(campaign)
    if not key:
        return None
    if key not in CAMPAIGNS:
        known = ", ".join(sorted(CAMPAIGNS))
        raise ValueError(f"Unknown campaign '{campaign}'. Known campaigns: {known}.")
    return CAMPAIGNS[key]


def normalize_campaign_key(campaign):
    return str(campaign or "").strip().lower().replace("-", "_").replace(" ", "_")


def apply_campaign_metadata(plan_entry, campaign_definition, slot_index):
    if not campaign_definition:
        return plan_entry

    sequence = campaign_definition.get("content_sequence") or []
    content_step = sequence[slot_index % len(sequence)] if sequence else {}
    offer = campaign_definition.get("active_offer") or {}
    enriched = dict(plan_entry)
    enriched.update(
        {
            "campaign": campaign_definition["campaign"],
            "series": campaign_definition["series"],
            "audience_lane": campaign_definition["audience_lane"],
            "content_goal": content_step.get("content_goal", "conversation"),
            "content_format": content_step.get("content_format", "series_post"),
            "cta_goal": content_step.get("cta_goal", "reply"),
            "campaign_prompt_guidance": content_step.get("prompt_guidance", ""),
            "campaign_strategy_note": campaign_definition.get("strategy_note", ""),
        }
    )
    if offer:
        enriched.update(build_offer_metadata(offer))
    return enriched


def apply_campaign_set_metadata(plan_entry, campaign_definition):
    if not campaign_definition:
        return plan_entry

    set_post = campaign_definition.get("set_post") or {}
    offer = campaign_definition.get("active_offer") or {}
    enriched = dict(plan_entry)
    enriched.update(
        {
            "campaign": campaign_definition["campaign"],
            "series": campaign_definition["series"],
            "audience_lane": campaign_definition["audience_lane"],
            "content_goal": set_post.get("content_goal", "product_connected"),
            "content_format": set_post.get("content_format", "series_set"),
            "cta_goal": set_post.get("cta_goal", "buy"),
            "campaign_prompt_guidance": set_post.get("prompt_guidance", ""),
            "campaign_strategy_note": campaign_definition.get("strategy_note", ""),
            "collection_title": set_post.get("title", campaign_definition["series"]),
        }
    )
    if offer:
        enriched.update(build_offer_metadata(offer))
    return enriched


def build_offer_metadata(offer):
    return {
        "active_offer": offer.get("description", ""),
        "discount_percent": offer.get("discount_percent"),
        "offer_scope": offer.get("scope", ""),
        "offer_starts_on": offer.get("starts_on", ""),
        "offer_ends_on": offer.get("ends_on", ""),
        "secondary_offer": offer.get("secondary_description", ""),
    }
