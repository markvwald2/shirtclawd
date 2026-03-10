from argparse import ArgumentParser

from bot.approval_queue import is_post_approved
from bot.x_publisher import DEFAULT_X_HANDLE, XPublisherError, load_posts, publish_post, select_post


def main():
    parser = ArgumentParser(description="Publish a generated ShirtClawd post to X.")
    parser.add_argument("--file", required=True, help="Path to a generated posts JSON file.")
    parser.add_argument("--index", type=int, default=None, help="Zero-based post index in the file.")
    parser.add_argument("--shirt-id", default=None, help="Select a post by shirt_id instead of index.")
    parser.add_argument("--handle", default=DEFAULT_X_HANDLE)
    parser.add_argument("--force", action="store_true", help="Allow live publishing without prior approval.")
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Actually publish to X. Without this flag, the command runs in dry-run mode.",
    )
    args = parser.parse_args()

    try:
        posts = load_posts(args.file)
        post = select_post(posts, index=args.index, shirt_id=args.shirt_id)

        if args.publish and not args.force and not is_post_approved(post, args.file, args.handle):
            raise XPublisherError(
                "Post is not approved for live publishing. Run approve_post.py first or use --force."
            )

        result = publish_post(post, dry_run=not args.publish, handle=args.handle)
    except XPublisherError as exc:
        print(exc)
        raise SystemExit(1) from exc

    if args.publish:
        print(f"Published to X as {args.handle}: tweet_id={result.get('tweet_id')}")
    else:
        print(f"Dry run only for {args.handle}. Generated X post preview:")
        print()
        print(result["text"])


if __name__ == "__main__":
    main()
