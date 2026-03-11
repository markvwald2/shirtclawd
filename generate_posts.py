import os
import time
from argparse import ArgumentParser
from datetime import datetime, timezone

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
    selected = select_shirts(inventory, history, max(args.count, 0))
    if not selected:
        print("No eligible shirts found. Check inventory status values and history.")
        return

    theme_formats = load_theme_formats()
    content_formats = load_content_formats()
    pricing = load_pricing()
    rng = random_source(args.seed)
    run_context = create_run_context(
        args.platform,
        args.writer_mode,
        args.ai_model,
        args.count,
        max_ai_calls=args.max_ai_calls,
        max_total_tokens=args.max_total_tokens,
        max_estimated_cost=args.max_estimated_cost,
    )
    posts, usage_events = build_posts_for_mode(
        shirts=selected,
        theme_formats=theme_formats,
        content_formats=content_formats,
        platform=args.platform,
        rng=rng,
        writer_mode=args.writer_mode,
        ai_model=args.ai_model,
        run_context=run_context,
        pricing=pricing,
    )
    now = datetime.now(timezone.utc)
    run_date = now.date().isoformat()
    destination = write_posts(posts, run_date, args.output_dir, args.platform)

    history_entries = [
        {
            "shirt_id": post["shirt_id"],
            "title": post["title"],
            "generated_at": now.isoformat(),
            "output_file": str(destination)
        }
        for post in posts
    ]
    append_history(history_entries, args.history)

    for event in usage_events:
        log_usage_event(event)

    summary = build_run_summary(run_context, posts, usage_events)
    summary_path = write_run_summary(summary, args.output_dir)

    print(f"Generated {len(posts)} posts -> {destination}")
    print(f"Run summary -> {summary_path}")


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
