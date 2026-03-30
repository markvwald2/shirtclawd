import json
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_INVENTORY_PATH = Path("data/shirt_inventory.json")
DEFAULT_ANNOTATIONS_PATH = Path("data/shirt_annotations.json")
REQUIRED_FIELDS = ("shirt_id", "title", "url", "image_url")
CANONICAL_STOREFRONT_URL = "https://www.thirdstringshirts.com/shop.html#!/"


def load_inventory(path=DEFAULT_INVENTORY_PATH, annotations_path=DEFAULT_ANNOTATIONS_PATH):
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

    annotations = load_annotations(annotations_path)
    normalized_inventory = []
    seen_ids = set()
    for index, record in enumerate(raw_inventory, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"Inventory record {index} must be a JSON object.")

        normalized = normalize_record(record, annotations.get(str(record.get("shirt_id", "")).strip(), {}))
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


def load_annotations(path=DEFAULT_ANNOTATIONS_PATH):
    annotations_path = Path(path)
    if not annotations_path.exists():
        return {}

    with annotations_path.open() as handle:
        raw_annotations = json.load(handle)

    if not isinstance(raw_annotations, dict):
        raise ValueError("Annotations dataset must be a JSON object keyed by shirt_id.")

    normalized = {}
    for shirt_id, entry in raw_annotations.items():
        if not isinstance(entry, dict):
            raise ValueError(f"Annotation for shirt_id {shirt_id} must be a JSON object.")
        normalized[str(shirt_id).strip()] = normalize_annotation(entry)
    return normalized


def normalize_record(record, annotation=None):
    annotation = annotation or {}
    title = first_value(record, "title", "shirt_name", "name")
    url = canonicalize_product_url(first_value(record, "url", "product_url"))
    status = str(record.get("status", "available")).strip().lower() or "available"
    tags = normalize_tags(record.get("tags"))
    target_audience = normalize_tags(annotation.get("target_audience"))

    return {
        "shirt_id": str(record.get("shirt_id", "")).strip(),
        "title": title,
        "url": url,
        "image_url": str(record.get("image_url", "")).strip(),
        "status": status,
        "tags": tags,
        "theme": first_non_empty(tags[:1] + [record.get("sub_theme"), record.get("theme")]),
        "description": str(record.get("description", "")).strip(),
        "promotion_status": annotation.get("promotion_status", "review"),
        "is_promotable": annotation.get("is_promotable", False),
        "reference_summary": annotation.get("reference_summary", ""),
        "target_audience": target_audience,
        "tone": annotation.get("tone", ""),
        "tone_notes": annotation.get("tone_notes", ""),
        "notes": annotation.get("notes", ""),
    }


def canonicalize_product_url(url):
    text = str(url or "").strip()
    if not text:
        return ""

    parsed = urlparse(text)
    hostname = (parsed.hostname or "").lower()
    if "myspreadshop." not in hostname:
        return text

    slug = parsed.path.lstrip("/")
    if not slug:
        return text

    query = parsed.query
    if query:
        return f"{CANONICAL_STOREFRONT_URL}{slug}?{query}"
    return f"{CANONICAL_STOREFRONT_URL}{slug}"


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


def normalize_annotation(entry):
    promotion_status = str(entry.get("promotion_status", "promote")).strip().lower() or "promote"
    if promotion_status not in {"promote", "skip", "review"}:
        promotion_status = "review"

    is_promotable = bool(entry.get("is_promotable", promotion_status == "promote"))

    return {
        "promotion_status": promotion_status,
        "is_promotable": is_promotable and promotion_status == "promote",
        "reference_summary": str(entry.get("reference_summary", "")).strip(),
        "target_audience": entry.get("target_audience", []),
        "tone": str(entry.get("tone", "")).strip(),
        "tone_notes": str(entry.get("tone_notes", "")).strip(),
        "notes": str(entry.get("notes", "")).strip(),
    }
