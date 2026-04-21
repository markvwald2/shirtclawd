from argparse import ArgumentParser

from bot.catalog_ops import CatalogError, add_inventory_shirt, upsert_shirt_annotation
from bot.data_loader import DEFAULT_ANNOTATIONS_PATH, DEFAULT_INVENTORY_PATH


def build_parser():
    parser = ArgumentParser(description="Add shirts to inventory and maintain promotable metadata.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add-shirt", help="Add a new shirt record to inventory.")
    add_parser.add_argument("--shirt-id", required=True)
    add_parser.add_argument("--title", required=True)
    add_parser.add_argument("--product-url", required=True)
    add_parser.add_argument("--image-url", required=True)
    add_parser.add_argument("--tag", action="append", default=[], help="Repeat or pass comma-separated values.")
    add_parser.add_argument("--theme", default="")
    add_parser.add_argument("--sub-theme", default="")
    add_parser.add_argument("--platform", default="Manual")
    add_parser.add_argument("--source-of-truth", default="local")
    add_parser.add_argument("--source-match", default="manual")
    add_parser.add_argument("--status", default="available")
    add_parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY_PATH))

    promote_parser = subparsers.add_parser("promote-shirt", help="Upsert promotable metadata for a shirt.")
    promote_parser.add_argument("--shirt-id", required=True)
    promote_parser.add_argument("--reference-summary", required=True)
    promote_parser.add_argument("--audience", action="append", default=[], help="Repeat or pass comma-separated values.")
    promote_parser.add_argument("--tone", default="")
    promote_parser.add_argument("--tone-notes", default="")
    promote_parser.add_argument("--notes", default="")
    promote_parser.add_argument("--promotion-status", default="promote", choices=("promote", "review", "skip"))
    promote_parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY_PATH))
    promote_parser.add_argument("--annotations", default=str(DEFAULT_ANNOTATIONS_PATH))

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "add-shirt":
            record = add_inventory_shirt(
                shirt_id=args.shirt_id,
                title=args.title,
                product_url=args.product_url,
                image_url=args.image_url,
                tags=args.tag,
                theme=args.theme,
                sub_theme=args.sub_theme,
                platform=args.platform,
                source_of_truth=args.source_of_truth,
                source_match=args.source_match,
                status=args.status,
                inventory_path=args.inventory,
            )
            print(f"Added shirt to inventory: {record['shirt_id']} -> {record['shirt_name']}")
        elif args.command == "promote-shirt":
            annotation = upsert_shirt_annotation(
                shirt_id=args.shirt_id,
                reference_summary=args.reference_summary,
                target_audience=args.audience,
                tone=args.tone,
                tone_notes=args.tone_notes,
                notes=args.notes,
                promotion_status=args.promotion_status,
                inventory_path=args.inventory,
                annotations_path=args.annotations,
            )
            print(
                f"Updated annotation for {args.shirt_id}: "
                f"promotion_status={annotation['promotion_status']} "
                f"is_promotable={annotation['is_promotable']}"
            )
    except CatalogError as exc:
        print(exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
