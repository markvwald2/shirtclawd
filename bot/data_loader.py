import json
from pathlib import Path


DEFAULT_INVENTORY_PATH = Path("data/shirt_inventory.json")
REQUIRED_FIELDS = ("shirt_id", "title", "url", "image_url")


def load_inventory(path=DEFAULT_INVENTORY_PATH):
    inventory_path = Path(path)
    if not inventory_path.exists():
        raise FileNotFoundError(
            f"Inventory dataset not found at {inventory_path}. "
            "Create data/shirt_inventory.json before running ClawdBot."
        )

    with inventory_path.open() as handle:
        raw_inventory = json.load(handle)

    if not isinstance(raw_inventory, list):
        raise ValueError("Inventory dataset must be a JSON array of shirt records.")

    normalized_inventory = []
    seen_ids = set()
    for index, record in enumerate(raw_inventory, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"Inventory record {index} must be a JSON object.")

        normalized = normalize_record(record)
        missing = [field for field in REQUIRED_FIELDS if not normalized.get(field)]
        if missing:
            raise ValueError(
                f"Inventory record {index} is missing required fields: {', '.join(missing)}"
            )

        shirt_id = normalized["shirt_id"]
        if shirt_id in seen_ids:
            continue

        seen_ids.add(shirt_id)
        normalized_inventory.append(normalized)

    return normalized_inventory


def normalize_record(record):
    title = first_value(record, "title", "shirt_name", "name")
    url = first_value(record, "url", "product_url")
    status = str(record.get("status", "available")).strip().lower() or "available"
    tags = normalize_tags(record.get("tags"))

    return {
        "shirt_id": str(record.get("shirt_id", "")).strip(),
        "title": title,
        "url": url,
        "image_url": str(record.get("image_url", "")).strip(),
        "status": status,
        "tags": tags,
        "theme": first_non_empty(tags[:1] + [record.get("sub_theme"), record.get("theme")]),
        "description": str(record.get("description", "")).strip(),
    }


def first_value(record, *keys):
    return first_non_empty(record.get(key) for key in keys)


def first_non_empty(values):
    for value in values:
        text = str(value).strip() if value is not None else ""
        if text:
            return text
    return ""


def normalize_tags(value):
    if isinstance(value, list):
        tags = value
    elif isinstance(value, str):
        tags = [part.strip() for part in value.split(",")]
    else:
        tags = []

    normalized = []
    seen = set()
    for tag in tags:
        text = str(tag).strip().lower()
        if text and text not in seen:
            seen.add(text)
            normalized.append(text)
    return normalized
