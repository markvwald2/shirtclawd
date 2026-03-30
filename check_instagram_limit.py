from argparse import ArgumentParser
import json

from bot.instagram_publisher import DEFAULT_INSTAGRAM_ACCOUNT_ID, InstagramPublisherError, get_content_publishing_limit


def main():
    parser = ArgumentParser(description="Check Instagram content publishing headroom.")
    parser.add_argument("--account-id", default=DEFAULT_INSTAGRAM_ACCOUNT_ID)
    args = parser.parse_args()

    try:
        state = get_content_publishing_limit(account_id=args.account_id)
    except InstagramPublisherError as exc:
        print(exc)
        raise SystemExit(1) from exc

    print(json.dumps(state))
    quota_total = state.get("quota_total")
    quota_usage = state.get("quota_usage", 0)
    if quota_total is not None and quota_usage >= quota_total:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
