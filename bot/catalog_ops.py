import json
from pathlib import Path

from bot.data_loader import DEFAULT_ANNOTATIONS_PATH, DEFAULT_INVENTORY_PATH


class CatalogError(RuntimeError):
    pass


def load_inventory_records(path=DEFAULT_INVENTORY_PATH):
    inventory_path = Path(path)
    if not inventory_path.exists():
        raise CatalogError(f"Inventory file not found: {inventory_path}")

    with inventory_path.open() as handle:
        payload = json.load(handle)

    if not isinstance(payload, list):
        raise CatalogError("Inventory file must contain a JSON array.")
    return payload


def load_annotation_records(path=DEFAULT_ANNOTATIONS_PATH):
    annotations_path = Path(path)
    if not annotations_path.exists():
        return {}

    with annotations_path.open() as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise CatalogError("Annotations file must contain a JSON object keyed by shirt_id.")
    return payload


def write_json(path, payload):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n")


def normalize_list(values):
    normalized = []
    seen = set()
    for value in values or []:
        parts = value if isinstance(value, list) else str(value).split(",")
        for part in parts:
            text = str(part).strip()
            lowered = text.lower()
            if text and lowered not in seen:
                seen.add(lowered)
                normalized.append(text)
    return normalized


def inventory_contains_shirt(shirt_id, inventory_path=DEFAULT_INVENTORY_PATH):
    resolved_shirt_id = str(shirt_id).strip()
    return any(
        str(record.get("shirt_id", "")).strip() == resolved_shirt_id
        for record in load_inventory_records(inventory_path)
    )


def add_inventory_shirt(
    *,
    shirt_id,
    title,
    product_url,
    image_url,
    inventory_path=DEFAULT_INVENTORY_PATH,
    tags=None,
    theme="",
    sub_theme="",
    platform="Manual",
    source_of_truth="local",
    source_match="manual",
    status="available",
):
    resolved_shirt_id = str(shirt_id).strip()
    resolved_title = str(title).strip()
    resolved_product_url = str(product_url).strip()
    resolved_image_url = str(image_url).strip()
    resolved_status = str(status).strip().lower() or "available"
    normalized_tags = [tag.lower() for tag in normalize_list(tags)]

    missing = []
    if not resolved_shirt_id:
        missing.append("shirt_id")
    if not resolved_title:
        missing.append("title")
    if not resolved_product_url:
        missing.append("product_url")
    if not resolved_image_url:
        missing.append("image_url")
    if missing:
        raise CatalogError(f"Missing required values: {', '.join(missing)}")

    inventory = load_inventory_records(inventory_path)
    if any(str(record.get("shirt_id", "")).strip() == resolved_shirt_id for record in inventory):
        raise CatalogError(f"shirt_id already exists in inventory: {resolved_shirt_id}")

    record = {
        "name": resolved_title,
        "URL": resolved_image_url,
        "sub_theme": str(sub_theme).strip(),
        "tags": normalized_tags,
        "theme": str(theme).strip(),
        "platform": str(platform).strip() or "Manual",
        "product_url": resolved_product_url,
        "idea_id": resolved_shirt_id,
        "source_of_truth": str(source_of_truth).strip() or "local",
        "source_match": str(source_match).strip() or "manual",
        "shirt_id": resolved_shirt_id,
        "shirt_name": resolved_title,
        "tone": "",
        "priority": "",
        "evergreen": None,
        "image_url": resolved_image_url,
        "status": resolved_status,
    }
    inventory.append(record)
    write_json(inventory_path, inventory)
    return record


def upsert_shirt_annotation(
    *,
    shirt_id,
    annotations_path=DEFAULT_ANNOTATIONS_PATH,
    inventory_path=DEFAULT_INVENTORY_PATH,
    promotion_status="promote",
    reference_summary="",
    target_audience=None,
    tone="",
    tone_notes="",
    notes="",
):
    resolved_shirt_id = str(shirt_id).strip()
    if not resolved_shirt_id:
        raise CatalogError("shirt_id is required.")
    if not inventory_contains_shirt(resolved_shirt_id, inventory_path=inventory_path):
        raise CatalogError(f"shirt_id was not found in inventory: {resolved_shirt_id}")

    resolved_promotion_status = str(promotion_status).strip().lower() or "promote"
    if resolved_promotion_status not in {"promote", "skip", "review"}:
        raise CatalogError("promotion_status must be one of: promote, skip, review")

    annotations = load_annotation_records(annotations_path)
    annotations[resolved_shirt_id] = {
        "promotion_status": resolved_promotion_status,
        "is_promotable": resolved_promotion_status == "promote",
        "reference_summary": str(reference_summary).strip(),
        "target_audience": normalize_list(target_audience),
        "tone": str(tone).strip(),
        "tone_notes": str(tone_notes).strip(),
        "notes": str(notes).strip(),
    }
    write_json(annotations_path, annotations)
    return annotations[resolved_shirt_id]
