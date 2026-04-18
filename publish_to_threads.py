from argparse import ArgumentParser
import os
from pathlib import Path


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

from bot.threads_publisher import (
    DEFAULT_THREADS_USERNAME,
    ThreadsPublisherError,
    load_posts,
    publish_post,
    select_post,
)


def main():
    parser = ArgumentParser(description="Publish a generated ShirtClawd post to Threads.")
    parser.add_argument("--file", required=True, help="Path to a generated posts JSON file.")
    parser.add_argument("--index", type=int, default=None, help="Zero-based post index in the file.")
    parser.add_argument("--shirt-id", default=None, help="Select a post by shirt_id instead of index.")
    parser.add_argument("--username", default=DEFAULT_THREADS_USERNAME)
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Actually publish to Threads. Without this flag, the command runs in dry-run mode.",
    )
    args = parser.parse_args()

    try:
        posts = load_posts(args.file)
        post = select_post(posts, index=args.index, shirt_id=args.shirt_id)
        result = publish_post(post, dry_run=not args.publish, username=args.username)
    except ThreadsPublisherError as exc:
        print(exc)
        raise SystemExit(1) from exc

    if args.publish:
        print(f"Published to Threads as {args.username}: id={result.get('threads_media_id')}")
    else:
        print(f"Dry run only for {args.username}. Generated Threads post preview:")
        print()
        print(result["text"])


if __name__ == "__main__":
    main()
