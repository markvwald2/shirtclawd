from argparse import ArgumentParser
import os
from pathlib import Path

from bot.data_loader import load_inventory
from bot.nl_commands import parse_command
from bot.post_generator import load_content_formats, load_theme_formats
from bot.selector import load_history, select_matching_shirts, select_shirts
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

    print(build_ask_response(parsed, shirts, generated, base_dir=Path.cwd()))


def append_generated_history(entries, history_path):
    from bot.selector import append_history

    if entries:
        append_history(entries, history_path)


def build_ask_response(parsed, shirts, generated, base_dir=None):
    base_dir = Path(base_dir) if base_dir else Path.cwd()
    destination = format_output_path(generated["destination"], base_dir)
    summary_path = format_output_path(generated["summary_path"], base_dir)

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
    return "\n".join(lines)


def format_output_path(path, base_dir):
    candidate = Path(path)
    try:
        return str(candidate.relative_to(base_dir))
    except ValueError:
        return str(candidate)


if __name__ == "__main__":
    main()
