from argparse import ArgumentParser

from bot.publish_runner import publish_approved_x_posts
from bot.x_publisher import DEFAULT_X_HANDLE, XPublisherError


def main():
    parser = ArgumentParser(description="Publish all approved X posts that have not already been published.")
    parser.add_argument("--handle", default=DEFAULT_X_HANDLE)
    parser.add_argument("--approval-queue", default=None)
    parser.add_argument("--publish-log", default="data/x_publish_log.jsonl")
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Actually publish approved posts. Without this flag, the command runs in dry-run mode.",
    )
    args = parser.parse_args()

    try:
        results = publish_approved_x_posts(
            approval_queue_path=args.approval_queue,
            publish_log_path=args.publish_log,
            handle=args.handle,
            dry_run=not args.publish,
        )
    except XPublisherError as exc:
        print(exc)
        raise SystemExit(1) from exc

    mode = "Published" if args.publish else "Dry-ran"
    print(f"{mode} {len(results)} approved X posts for {args.handle}")


if __name__ == "__main__":
    main()
