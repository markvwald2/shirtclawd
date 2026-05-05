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

from bot.facebook_publisher import (
    DEFAULT_FACEBOOK_PAGE_ID,
    FacebookPublisherError,
    load_posts,
    publish_post,
    select_post,
)


def main():
    parser = ArgumentParser(description="Publish a generated ShirtClawd post to Facebook.")
    parser.add_argument("--file", required=True, help="Path to a generated posts JSON file.")
    parser.add_argument("--index", type=int, default=None, help="Zero-based post index in the file.")
    parser.add_argument("--shirt-id", default=None, help="Select a post by shirt_id instead of index.")
    parser.add_argument("--all", action="store_true", help="Publish every post in the file in order.")
    parser.add_argument("--page-id", default=DEFAULT_FACEBOOK_PAGE_ID)
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Actually publish to Facebook. Without this flag, the command runs in dry-run mode.",
    )
    args = parser.parse_args()

    try:
        posts = load_posts(args.file)
        selected_posts = posts if args.all else [select_post(posts, index=args.index, shirt_id=args.shirt_id)]
        results = [publish_post(post, dry_run=not args.publish, page_id=args.page_id) for post in selected_posts]
    except FacebookPublisherError as exc:
        print(exc)
        raise SystemExit(1) from exc

    if args.publish:
        for result in results:
            label = "multi-photo post" if result.get("is_multi_image") else "post"
            print(f"Published Facebook {label} to page {args.page_id}: post_id={result.get('facebook_post_id')}")
    else:
        for index, result in enumerate(results):
            print(f"Dry run only for Facebook page {args.page_id}. Generated Facebook post preview {index}:")
            print()
            print(result["message"])
            print()


if __name__ == "__main__":
    main()
