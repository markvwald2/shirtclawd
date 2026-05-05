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

from bot.instagram_publisher import DEFAULT_INSTAGRAM_ACCOUNT_ID, InstagramPublisherError, load_posts, publish_post, select_post


def main():
    parser = ArgumentParser(description="Publish a generated ShirtClawd post to Instagram.")
    parser.add_argument("--file", required=True, help="Path to a generated posts JSON file.")
    parser.add_argument("--index", type=int, default=None, help="Zero-based post index in the file.")
    parser.add_argument("--shirt-id", default=None, help="Select a post by shirt_id instead of index.")
    parser.add_argument("--all", action="store_true", help="Publish every post in the file in order.")
    parser.add_argument("--account-id", default=DEFAULT_INSTAGRAM_ACCOUNT_ID)
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Actually publish to Instagram. Without this flag, the command runs in dry-run mode.",
    )
    args = parser.parse_args()

    try:
        posts = load_posts(args.file)
        selected_posts = posts if args.all else [select_post(posts, index=args.index, shirt_id=args.shirt_id)]
        results = [
            publish_post(post, dry_run=not args.publish, account_id=args.account_id)
            for post in selected_posts
        ]
    except InstagramPublisherError as exc:
        print(exc)
        raise SystemExit(1) from exc

    if args.publish:
        for result in results:
            label = "carousel" if result.get("is_carousel") else "post"
            print(
                f"Published Instagram {label} to account {args.account_id}: "
                f"media_id={result.get('instagram_media_id')}"
            )
    else:
        for index, result in enumerate(results):
            print(f"Dry run only for Instagram account {args.account_id}. Caption preview {index}:")
            print()
            print(result["caption"])
            print()


if __name__ == "__main__":
    main()
