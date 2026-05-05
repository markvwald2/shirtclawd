import os
from argparse import ArgumentParser

from bot.ai_writer import DEFAULT_AI_MODEL
from bot.data_loader import load_inventory
from bot.planner import (
    DEFAULT_DAILY_SPEND_LIMIT_USD,
    DEFAULT_ESTIMATED_INPUT_TOKENS,
    DEFAULT_ESTIMATED_OUTPUT_TOKENS,
    DEFAULT_PLATFORMS,
    build_daily_plan,
)
from bot.selector import load_history
from bot.usage_logger import load_pricing
from bot.writer import write_daily_plan


def main():
    parser = ArgumentParser(description="Build a daily ClawdBot posting plan.")
    parser.add_argument("--inventory", default="data/shirt_inventory.json")
    parser.add_argument("--history", default="data/promotion_history.json")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--date")
    parser.add_argument("--platform", dest="platforms", action="append")
    parser.add_argument("--ai-model", default=os.getenv("OPENAI_MODEL", DEFAULT_AI_MODEL))
    parser.add_argument("--max-estimated-cost", type=float, default=DEFAULT_DAILY_SPEND_LIMIT_USD)
    parser.add_argument("--expected-input-tokens", type=int, default=DEFAULT_ESTIMATED_INPUT_TOKENS)
    parser.add_argument("--expected-output-tokens", type=int, default=DEFAULT_ESTIMATED_OUTPUT_TOKENS)
    parser.add_argument("--campaign", help="Optional campaign mode, e.g. coloradans_against.")
    parser.add_argument(
        "--include-campaign-set-post",
        action="store_true",
        help="Add one campaign collection/set post, e.g. an Instagram carousel for a shirt line.",
    )
    parser.add_argument("--campaign-set-platform", dest="campaign_set_platforms", action="append")
    parser.add_argument("--campaign-set-size", type=int, default=4)
    parser.add_argument("--approval-required", dest="approval_required", action="store_true")
    parser.add_argument("--no-approval-required", dest="approval_required", action="store_false")
    parser.set_defaults(approval_required=True)
    args = parser.parse_args()

    inventory = load_inventory(args.inventory)
    history = load_history(args.history)
    pricing = load_pricing()
    platforms = args.platforms or list(DEFAULT_PLATFORMS)

    plan = build_daily_plan(
        inventory=inventory,
        history=history,
        pricing=pricing,
        ai_model=args.ai_model,
        plan_date=args.date,
        platforms=platforms,
        max_estimated_cost=args.max_estimated_cost,
        approval_required=args.approval_required,
        expected_input_tokens=args.expected_input_tokens,
        expected_output_tokens=args.expected_output_tokens,
        campaign=args.campaign,
        include_campaign_set_post=args.include_campaign_set_post,
        campaign_set_platforms=args.campaign_set_platforms,
        campaign_set_size=args.campaign_set_size,
    )
    destination = write_daily_plan(plan, args.output_dir)

    print(f"Planned {len(plan['planned_posts'])} posts -> {destination}")
    estimated_cost = plan["estimates"]["estimated_total_ai_cost_usd"]
    if estimated_cost is not None:
        print(f"Estimated AI cost -> ${estimated_cost:.6f}")


if __name__ == "__main__":
    main()
