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
SUPPORTED_WRITER_MODES = ("ai",)
PUBLISH_LOG_PATHS = {
    "instagram": Path("data/instagram_publish_log.jsonl"),
    "bluesky": Path("data/bluesky_publish_log.jsonl"),
    "x": Path("data/x_publish_log.jsonl"),
}


def main():
    parser = ArgumentParser(description="Generate deterministic marketing posts from shirt inventory.")
    parser.add_argument("--inventory", default="data/shirt_inventory.json")
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--history", default="data/promotion_history.json")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--plan", default=None, help="Path to a daily plan JSON file.")
    parser.add_argument("--platform", choices=SUPPORTED_PLATFORMS, default="instagram")
    parser.add_argument("--writer-mode", choices=SUPPORTED_WRITER_MODES, default="ai")
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
    validate_writer_mode(args.writer_mode)

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
    validate_writer_mode(plan.get("writer_mode", args.writer_mode), source=f"plan {args.plan}")
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
    recent_posts = load_recent_platform_posts(platform)
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
        recent_posts=recent_posts,
    )

    if plan_entries:
        for post, entry in zip(posts, plan_entries):
            post.update(plan_metadata(entry, plan_date))

    now = datetime.now(timezone.utc)
    run_date = plan_date or now.date().isoformat()
    destination = write_posts(
        posts,
        run_date,
        output_dir,
        platform,
        run_id=run_context["run_id"],
    )

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


def build_posts_for_mode(
    shirts,
    theme_formats,
    content_formats,
    platform,
    rng,
    writer_mode,
    ai_model,
    run_context,
    pricing,
    recent_posts=None,
):
    validate_writer_mode(writer_mode)

    posts = []
    usage_events = []
    recent_posts = list(recent_posts or [])
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
                    status="budget_exceeded",
                    error=message,
                    pricing=pricing,
                )
            )
            for event in usage_events:
                log_usage_event(event)
            print(f"{message}; stopping before generating {shirt['title']}.")
            raise SystemExit(1)

        started = time.perf_counter()
        try:
            response = generate_post_components(
                shirt=shirt,
                platform=platform,
                model=ai_model,
                recent_posts=recent_posts,
            )
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            post = build_ai_post(shirt, response["components"], content_formats, platform, rng)
            posts.append(post)
            recent_posts.append(
                {
                    "caption": post["caption"],
                    "hashtags": post["hashtags"],
                }
            )
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

    return posts, usage_events


def validate_writer_mode(writer_mode, source="request"):
    if writer_mode not in SUPPORTED_WRITER_MODES:
        supported = ", ".join(SUPPORTED_WRITER_MODES)
        raise SystemExit(
            f"Unsupported writer mode '{writer_mode}' in {source}. "
            f"Supported writer modes: {supported}. Rule-based fallback has been removed."
        )


def load_recent_platform_posts(platform, limit=12):
    path = PUBLISH_LOG_PATHS.get(platform)
    if path is None or not path.exists():
        return []

    posts = []
    with path.open() as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            text = str(payload.get("caption") or payload.get("text") or payload.get("body") or "").strip()
            hashtags = [token for token in text.split() if token.startswith("#")]
            posts.append({"caption": text, "hashtags": hashtags})

    return posts[-limit:]


if __name__ == "__main__":
    main()
