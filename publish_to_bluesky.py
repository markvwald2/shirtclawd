from argparse import ArgumentParser

from bot.approval_queue import DEFAULT_BLUESKY_APPROVAL_QUEUE_PATH, is_post_approved
from bot.bluesky_publisher import (
    DEFAULT_BLUESKY_HANDLE,
    BlueskyPublisherError,
    load_posts,
    publish_post,
    select_post,
)


def main():
    parser = ArgumentParser(description="Publish a generated ShirtClawd post to Bluesky.")
    parser.add_argument("--file", required=True, help="Path to a generated posts JSON file.")
    parser.add_argument("--index", type=int, default=None, help="Zero-based post index in the file.")
    parser.add_argument("--shirt-id", default=None, help="Select a post by shirt_id instead of index.")
    parser.add_argument("--handle", default=DEFAULT_BLUESKY_HANDLE)
    parser.add_argument("--force", action="store_true", help="Allow live publishing without prior approval.")
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Actually publish to Bluesky. Without this flag, the command runs in dry-run mode.",
    )
    args = parser.parse_args()

    try:
        posts = load_posts(args.file)
        post = select_post(posts, index=args.index, shirt_id=args.shirt_id)

        if args.publish and not args.force and not is_post_approved(
            post,
            args.file,
            args.handle,
            path=DEFAULT_BLUESKY_APPROVAL_QUEUE_PATH,
            platform="bluesky",
        ):
            raise BlueskyPublisherError(
                "Post is not approved for live publishing. Run approve_post.py --platform bluesky first or use --force."
            )

        result = publish_post(post, dry_run=not args.publish, handle=args.handle)
    except BlueskyPublisherError as exc:
        print(exc)
        raise SystemExit(1) from exc

    if args.publish:
        print(f"Published to Bluesky as {args.handle}: uri={result.get('uri')}")
    else:
        print(f"Dry run only for {args.handle}. Generated Bluesky post preview:")
        print()
        print(result["text"])


if __name__ == "__main__":
    main()
