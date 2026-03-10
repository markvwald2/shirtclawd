from argparse import ArgumentParser

from bot.approval_queue import approve_post
from bot.x_publisher import DEFAULT_X_HANDLE, XPublisherError, load_posts, select_post


def main():
    parser = ArgumentParser(description="Approve a generated ShirtClawd post for X publishing.")
    parser.add_argument("--file", required=True, help="Path to a generated posts JSON file.")
    parser.add_argument("--index", type=int, default=None, help="Zero-based post index in the file.")
    parser.add_argument("--shirt-id", default=None, help="Select a post by shirt_id instead of index.")
    parser.add_argument("--handle", default=DEFAULT_X_HANDLE)
    args = parser.parse_args()

    try:
        posts = load_posts(args.file)
        post = select_post(posts, index=args.index, shirt_id=args.shirt_id)
        approve_post(post, args.file, args.handle)
    except XPublisherError as exc:
        print(exc)
        raise SystemExit(1) from exc

    print(f"Approved for X publishing: {post.get('title')} -> {args.handle}")


if __name__ == "__main__":
    main()
