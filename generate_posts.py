import os
import time
from argparse import ArgumentParser
from datetime import datetime, timezone
import json
from pathlib import Path

from bot.ai_writer import AIWriterError, DEFAULT_AI_MODEL, generate_post_components
from bot.data_loader import load_inventory
from bot.inventory_sync import DEFAULT_SOURCE_URL, InventorySyncError, sync_inventory
from bot.post_generator import (
    build_ai_post,
    build_posts,
    build_rule_based_post,
    load_content_formats,
    load_theme_formats,
    random_source
)
from bot.selector import append_history, load_history, select_shirts
from bot.usage_logger import (
    budget_status,
    build_run_summary,
    build_usage_event,
    create_run_context,
    load_pricing,
    log_usage_event,
    set_budget_trigger,
    update_budget_state,
    write_run_summary,
)
from bot.writer import write_posts

DEFAULT_MAX_AI_CALLS = 3
DEFAULT_MAX_TOTAL_TOKENS = 12000
DEFAULT_MAX_ESTIMATED_COST = 0.02
SUPPORTED_PLATFORMS = ("instagram", "facebook", "x", "bluesky", "reels", "tiktok")


def main():
    parser = ArgumentParser(description="Generate deterministic marketing posts from shirt inventory.")
    parser.add_argument("--inventory", default="data/shirt_inventory.json")
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--history", default="data/promotion_history.json")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--plan", default=None, help="Path to a daily plan JSON file.")
    parser.add_argument("--platform", choices=SUPPORTED_PLATFORMS, default="instagram")
    parser.add_argument("--writer-mode", choices=("auto", "rule", "ai"), default="auto")
    parser.add_argument("--ai-model", default=os.getenv("OPENAI_MODEL", DEFAULT_AI_MODEL))
    parser.add_argument("--max-ai-calls", type=int, default=DEFAULT_MAX_AI_CALLS)
    parser.add_argument("--max-total-tokens", type=int, default=DEFAULT_MAX_TOTAL_TOKENS)
    parser.add_argument("--max-estimated-cost", type=float, default=DEFAULT_MAX_ESTIMATED_COST)
    parser.add_argument("--refresh-inventory", action="store_true")
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    args = parser.parse_args()

    if args.refresh_inventory:
        try:
            metadata = sync_inventory(source_url=args.source_url, destination=args.inventory)
        except InventorySyncError as exc:
            print(exc)
            raise SystemExit(1) from exc
        print(
            "Refreshed inventory before generation: "
            f"{metadata['record_count']} records from {metadata['source_url']}"
        )

    inventory = load_inventory(args.inventory)
    history = load_history(args.history)

    theme_formats = load_theme_formats()
    content_formats = load_content_formats()
    pricing = load_pricing()
    if args.plan:
        generate_from_plan(args, inventory, theme_formats, content_formats, pricing)
        return

    selected = select_shirts(inventory, history, max(args.count, 0))
    if not selected:
        print("No eligible shirts found. Check inventory status values and history.")
        return

    generated = generate_for_platform(
        shirts=selected,
        platform=args.platform,
        writer_mode=args.writer_mode,
        ai_model=args.ai_model,
        seed=args.seed,
        output_dir=args.output_dir,
        pricing=pricing,
        theme_formats=theme_formats,
        content_formats=content_formats,
        max_ai_calls=args.max_ai_calls,
        max_total_tokens=args.max_total_tokens,
        max_estimated_cost=args.max_estimated_cost,
    )
    append_history(generated["history_entries"], args.history)

    print(f"Generated {len(generated['posts'])} posts -> {generated['destination']}")
    print(f"Run summary -> {generated['summary_path']}")


def generate_from_plan(args, inventory, theme_formats, content_formats, pricing):
    plan = load_daily_plan(args.plan)
    inventory_by_id = {shirt["shirt_id"]: shirt for shirt in inventory}
    grouped_entries = {}
    for entry in plan.get("planned_posts", []):
        platform = entry.get("platform")
        if not platform:
            continue
        grouped_entries.setdefault(platform, []).append(entry)

    if not grouped_entries:
        print("Daily plan has no planned posts.")
        return

    history_entries = []
    total_posts = 0
    for platform, entries in grouped_entries.items():
        shirts = []
        for entry in entries:
            shirt_id = entry.get("shirt_id")
            if shirt_id not in inventory_by_id:
                raise SystemExit(f"Planned shirt_id {shirt_id} was not found in the current inventory.")
            shirts.append(inventory_by_id[shirt_id])

        generated = generate_for_platform(
            shirts=shirts,
            platform=platform,
            writer_mode=plan.get("writer_mode", args.writer_mode),
            ai_model=plan.get("ai_model", args.ai_model),
            seed=args.seed,
            output_dir=args.output_dir,
            pricing=pricing,
            theme_formats=theme_formats,
            content_formats=content_formats,
            max_ai_calls=args.max_ai_calls,
            max_total_tokens=args.max_total_tokens,
            max_estimated_cost=args.max_estimated_cost,
            plan_entries=entries,
            plan_date=plan.get("plan_date"),
        )
        history_entries.extend(generated["history_entries"])
        total_posts += len(generated["posts"])
        print(f"Generated {len(generated['posts'])} {platform} posts -> {generated['destination']}")
        print(f"Run summary -> {generated['summary_path']}")

    if history_entries:
        append_history(history_entries, args.history)
    print(f"Generated {total_posts} total posts from plan {args.plan}")


def generate_for_platform(
    shirts,
    platform,
    writer_mode,
    ai_model,
    seed,
    output_dir,
    pricing,
    theme_formats,
    content_formats,
    max_ai_calls,
    max_total_tokens,
    max_estimated_cost,
    plan_entries=None,
    plan_date=None,
):
    rng = random_source(seed)
    run_context = create_run_context(
        platform,
        writer_mode,
        ai_model,
        len(shirts),
        max_ai_calls=max_ai_calls,
        max_total_tokens=max_total_tokens,
        max_estimated_cost=max_estimated_cost,
    )
    posts, usage_events = build_posts_for_mode(
        shirts=shirts,
        theme_formats=theme_formats,
        content_formats=content_formats,
        platform=platform,
        rng=rng,
        writer_mode=writer_mode,
        ai_model=ai_model,
        run_context=run_context,
        pricing=pricing,
    )

    if plan_entries:
        for post, entry in zip(posts, plan_entries):
            post.update(plan_metadata(entry, plan_date))

    now = datetime.now(timezone.utc)
    run_date = plan_date or now.date().isoformat()
    destination = write_posts(posts, run_date, output_dir, platform)

    history_entries = [
        {
            "shirt_id": post["shirt_id"],
            "title": post["title"],
            "generated_at": now.isoformat(),
            "output_file": str(destination),
        }
        for post in posts
    ]

    for event in usage_events:
        log_usage_event(event)

    summary = build_run_summary(run_context, posts, usage_events)
    summary_path = write_run_summary(summary, output_dir)
    return {
        "posts": posts,
        "destination": destination,
        "history_entries": history_entries,
        "summary_path": summary_path,
    }


def load_daily_plan(path):
    with Path(path).open() as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Daily plan must be a JSON object.")
    return payload


def plan_metadata(entry, plan_date):
    return {
        "plan_slot": entry.get("slot"),
        "approval_required": bool(entry.get("approval_required")),
        "approval_status": entry.get("approval_status", "pending"),
        "planned_platform": entry.get("platform"),
        "plan_date": plan_date,
    }


def build_posts_for_mode(shirts, theme_formats, content_formats, platform, rng, writer_mode, ai_model, run_context, pricing):
    if writer_mode == "rule":
        return build_posts(shirts, theme_formats, content_formats, platform, rng), []

    posts = []
    usage_events = []
    for shirt in shirts:
        triggered_limit = budget_status(run_context)
        if triggered_limit:
            message = f"Budget guard triggered ({triggered_limit})"
            set_budget_trigger(run_context, triggered_limit)
            usage_events.append(
                build_usage_event(
                    run_context=run_context,
                    shirt=shirt,
                    platform=platform,
                    model=ai_model,
                    writer_mode=writer_mode,
                    status="budget_fallback",
                    error=message,
                    pricing=pricing,
                )
            )
            print(f"{message}; falling back to rule-based copy for {shirt['title']}.")
            posts.append(build_rule_based_post(shirt, theme_formats, content_formats, platform, rng))
            continue

        if writer_mode in {"auto", "ai"}:
            started = time.perf_counter()
            try:
                response = generate_post_components(
                    shirt=shirt,
                    platform=platform,
                    model=ai_model
                )
                latency_ms = round((time.perf_counter() - started) * 1000, 2)
                posts.append(build_ai_post(shirt, response["components"], content_formats, platform, rng))
                usage_events.append(
                    build_usage_event(
                        run_context=run_context,
                        shirt=shirt,
                        platform=platform,
                        model=ai_model,
                        writer_mode="ai",
                        status="success",
                        usage=response.get("usage", {}),
                        latency_ms=latency_ms,
                        pricing=pricing,
                    )
                )
                update_budget_state(run_context, usage_events[-1])
                continue
            except AIWriterError as exc:
                latency_ms = round((time.perf_counter() - started) * 1000, 2)
                if writer_mode == "ai":
                    usage_events.append(
                        build_usage_event(
                            run_context=run_context,
                            shirt=shirt,
                            platform=platform,
                            model=ai_model,
                            writer_mode="ai",
                            status="error",
                            latency_ms=latency_ms,
                            error=str(exc),
                            pricing=pricing,
                        )
                    )
                    for event in usage_events:
                        log_usage_event(event)
                    print(exc)
                    raise SystemExit(1) from exc

                usage_events.append(
                    build_usage_event(
                        run_context=run_context,
                        shirt=shirt,
                        platform=platform,
                        model=ai_model,
                        writer_mode="auto",
                        status="fallback",
                        latency_ms=latency_ms,
                        error=str(exc),
                        pricing=pricing,
                    )
                )
                print(f"AI writer unavailable for {shirt['title']}, falling back to rule-based copy: {exc}")

        posts.append(build_rule_based_post(shirt, theme_formats, content_formats, platform, rng))

    return posts, usage_events


if __name__ == "__main__":
    main()
