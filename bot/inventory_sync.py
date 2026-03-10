import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


DEFAULT_SOURCE_URL = (
    "https://raw.githubusercontent.com/markvwald2/thirdstringshirts/master/data/shirt_inventory.json"
)
DEFAULT_INVENTORY_PATH = Path("data/shirt_inventory.json")
DEFAULT_METADATA_PATH = Path("data/inventory_metadata.json")
DEFAULT_SNAPSHOT_DIR = Path("data/snapshots")


class InventorySyncError(RuntimeError):
    pass


def sync_inventory(
    source_url=DEFAULT_SOURCE_URL,
    destination=DEFAULT_INVENTORY_PATH,
    metadata_path=DEFAULT_METADATA_PATH,
    snapshot_dir=DEFAULT_SNAPSHOT_DIR,
):
    try:
        payload = fetch_inventory_payload(source_url)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise InventorySyncError(f"Failed to fetch inventory from {source_url}: {exc}") from exc

    try:
        inventory = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise InventorySyncError(
            f"Fetched inventory from {source_url} was not valid JSON: {exc}"
        ) from exc

    if not isinstance(inventory, list):
        raise InventorySyncError("Fetched inventory payload must be a JSON array.")

    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_text(format_json(inventory))

    fetched_at = datetime.now(timezone.utc)
    snapshot_path = write_snapshot(snapshot_dir, inventory, fetched_at)
    metadata = build_metadata(source_url, destination_path, snapshot_path, payload, inventory, fetched_at)
    metadata_destination = Path(metadata_path)
    metadata_destination.parent.mkdir(parents=True, exist_ok=True)
    metadata_destination.write_text(format_json(metadata))

    return metadata


def fetch_inventory_payload(source_url):
    with urlopen(source_url, timeout=30) as response:
        return response.read().decode("utf-8")


def write_snapshot(snapshot_dir, inventory, fetched_at):
    destination = Path(snapshot_dir)
    destination.mkdir(parents=True, exist_ok=True)
    snapshot_path = destination / f"shirt_inventory_{fetched_at.strftime('%Y%m%dT%H%M%SZ')}.json"
    snapshot_path.write_text(format_json(inventory))
    return snapshot_path


def build_metadata(source_url, destination_path, snapshot_path, payload, inventory, fetched_at):
    return {
        "source_url": source_url,
        "fetched_at": fetched_at.isoformat(),
        "destination": str(destination_path),
        "snapshot_path": str(snapshot_path),
        "record_count": len(inventory),
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    }


def format_json(payload):
    return json.dumps(payload, indent=2) + "\n"
