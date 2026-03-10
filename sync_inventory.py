from argparse import ArgumentParser

from bot.inventory_sync import (
    DEFAULT_INVENTORY_PATH,
    DEFAULT_METADATA_PATH,
    DEFAULT_SNAPSHOT_DIR,
    DEFAULT_SOURCE_URL,
    InventorySyncError,
    sync_inventory,
)


def main():
    parser = ArgumentParser(description="Sync ClawdBot inventory from the public source-of-truth dataset.")
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    parser.add_argument("--destination", default=str(DEFAULT_INVENTORY_PATH))
    parser.add_argument("--metadata-path", default=str(DEFAULT_METADATA_PATH))
    parser.add_argument("--snapshot-dir", default=str(DEFAULT_SNAPSHOT_DIR))
    args = parser.parse_args()

    try:
        metadata = sync_inventory(
            source_url=args.source_url,
            destination=args.destination,
            metadata_path=args.metadata_path,
            snapshot_dir=args.snapshot_dir,
        )
    except InventorySyncError as exc:
        print(exc)
        raise SystemExit(1) from exc

    print(
        "Synced inventory: "
        f"{metadata['record_count']} records -> {metadata['destination']} "
        f"(snapshot: {metadata['snapshot_path']})"
    )


if __name__ == "__main__":
    main()
