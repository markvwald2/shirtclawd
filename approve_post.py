from argparse import ArgumentParser

from bot.approval_queue import DEFAULT_BLUESKY_APPROVAL_QUEUE_PATH, DEFAULT_APPROVAL_QUEUE_PATH, approve_post
from bot.bluesky_publisher import DEFAULT_BLUESKY_HANDLE
from bot.x_publisher import DEFAULT_X_HANDLE, XPublisherError, load_posts, select_post


def main():
    parser = ArgumentParser(description="Approve a generated ShirtClawd post for X publishing.")
    parser.add_argument("--file", required=True, help="Path to a generated posts JSON file.")
    parser.add_argument("--index", type=int, default=None, help="Zero-based post index in the file.")
    parser.add_argument("--shirt-id", default=None, help="Select a post by shirt_id instead of index.")
    parser.add_argument("--platform", choices=("x", "bluesky"), default="x")
    parser.add_argument("--handle", default=None)
    args = parser.parse_args()

    try:
        posts = load_posts(args.file)
        post = select_post(posts, index=args.index, shirt_id=args.shirt_id)
        platform_defaults = {
            "x": (DEFAULT_X_HANDLE, DEFAULT_APPROVAL_QUEUE_PATH),
            "bluesky": (DEFAULT_BLUESKY_HANDLE, DEFAULT_BLUESKY_APPROVAL_QUEUE_PATH),
        }
        default_handle, queue_path = platform_defaults[args.platform]
        handle = args.handle or default_handle
        approve_post(post, args.file, handle, path=queue_path, platform=args.platform)
    except XPublisherError as exc:
        print(exc)
        raise SystemExit(1) from exc

    print(f"Approved for {args.platform} publishing: {post.get('title')} -> {handle}")


if __name__ == "__main__":
    main()
