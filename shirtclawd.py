from argparse import ArgumentParser
import os
from pathlib import Path

from bot.bluesky_publisher import BlueskyPublisherError, publish_post as publish_bluesky_post
from bot.data_loader import load_inventory
from bot.facebook_publisher import FacebookPublisherError, publish_post as publish_facebook_post
from bot.instagram_publisher import InstagramPublisherError, publish_post as publish_instagram_post
from bot.nl_commands import parse_command
from bot.post_generator import load_content_formats, load_theme_formats
from bot.selector import load_history, select_matching_shirts, select_shirts
from bot.threads_publisher import ThreadsPublisherError, publish_post as publish_threads_post
from bot.usage_logger import load_pricing
from generate_posts import (
    DEFAULT_AI_MODEL,
    DEFAULT_MAX_AI_CALLS,
    DEFAULT_MAX_ESTIMATED_COST,
    DEFAULT_MAX_TOTAL_TOKENS,
    generate_for_platform,
)


def load_env_file(path=".env"):
    env_path = Path(path)
    if not env_path.exists():
        return

    for line in env_path.read_text().splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file()


def main():
    parser = ArgumentParser(description="Natural-language command runner for ShirtClawd.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ask_parser = subparsers.add_parser("ask", help="Run a natural-language ShirtClawd command.")
    ask_parser.add_argument("prompt", help='Example: "Write 2 posts for Instagram for the Coloradans Against shirts"')
    ask_parser.add_argument("--inventory", default="data/shirt_inventory.json")
    ask_parser.add_argument("--history", default="data/promotion_history.json")
    ask_parser.add_argument("--output-dir", default="output")
    ask_parser.add_argument("--seed", type=int, default=7)
    ask_parser.add_argument("--ai-model", default=DEFAULT_AI_MODEL)
    ask_parser.add_argument("--max-ai-calls", type=int, default=DEFAULT_MAX_AI_CALLS)
    ask_parser.add_argument("--max-total-tokens", type=int, default=DEFAULT_MAX_TOTAL_TOKENS)
    ask_parser.add_argument("--max-estimated-cost", type=float, default=DEFAULT_MAX_ESTIMATED_COST)
    ask_parser.add_argument(
        "--publish",
        action="store_true",
        help="Generate and immediately publish supported platforms like Instagram and Bluesky.",
    )
    args = parser.parse_args()

    if args.command == "ask":
        run_ask(args)


def run_ask(args):
    parsed = parse_command(args.prompt)
    inventory = load_inventory(args.inventory)
    history = load_history(args.history)
    pricing = load_pricing()
    theme_formats = load_theme_formats()
    content_formats = load_content_formats()

    if parsed.query:
        shirts = select_matching_shirts(inventory, history, parsed.count, parsed.query)
    else:
        shirts = select_shirts(inventory, history, parsed.count)

    if not shirts:
        detail = f" matching '{parsed.query}'" if parsed.query else ""
        raise SystemExit(f"No eligible shirts found{detail}.")

    generated = generate_for_platform(
        shirts=shirts,
        platform=parsed.platform,
        writer_mode="ai",
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
    append_generated_history(generated["history_entries"], args.history)

    publish_results = []
    if args.publish:
        publish_results = publish_generated_posts(parsed.platform, generated["posts"])

    print(build_ask_response(parsed, shirts, generated, publish_results=publish_results, base_dir=Path.cwd()))


def append_generated_history(entries, history_path):
    from bot.selector import append_history

    if entries:
        append_history(entries, history_path)


def publish_generated_posts(platform, posts):
    if platform == "instagram":
        publisher = publish_instagram_post
        handled_error = InstagramPublisherError
    elif platform == "facebook":
        publisher = publish_facebook_post
        handled_error = FacebookPublisherError
    elif platform == "bluesky":
        publisher = publish_bluesky_post
        handled_error = BlueskyPublisherError
    elif platform == "threads":
        publisher = publish_threads_post
        handled_error = ThreadsPublisherError
    else:
        raise SystemExit(
            f"Direct publish is not supported for platform '{platform}'. "
            "Use generate-only mode or a dedicated publisher command."
        )

    results = []
    for post in posts:
        try:
            results.append(publisher(post, dry_run=False))
        except handled_error as exc:
            raise SystemExit(f"Publishing failed for {post.get('title', 'untitled post')}: {exc}") from exc
    return results


def build_ask_response(parsed, shirts, generated, publish_results=None, base_dir=None):
    base_dir = Path(base_dir) if base_dir else Path.cwd()
    destination = format_output_path(generated["destination"], base_dir)
    summary_path = format_output_path(generated["summary_path"], base_dir)
    publish_results = publish_results or []

    lines = [
        f"Ready: {len(generated['posts'])} {parsed.platform} post{'s' if len(generated['posts']) != 1 else ''}.",
    ]
    if parsed.query:
        lines.append(f"Matched: {parsed.query}.")
    lines.append("Selected designs:")
    for shirt in shirts:
        lines.append(f"- {shirt['title']}")
    lines.append(f"Posts file: {destination}")
    lines.append(f"Run summary: {summary_path}")
    if publish_results:
        lines.append("Published:")
        for result in publish_results:
            identifier = (
                result.get("instagram_media_id")
                or result.get("facebook_post_id")
                or result.get("uri")
                or result.get("threads_media_id")
                or "ok"
            )
            lines.append(f"- {result.get('title', 'Untitled')} -> {identifier}")
    return "\n".join(lines)


def format_output_path(path, base_dir):
    candidate = Path(path)
    try:
        return str(candidate.relative_to(base_dir))
    except ValueError:
        return str(candidate)


if __name__ == "__main__":
    main()
