import json
from pathlib import Path


DEFAULT_HISTORY_PATH = Path("data/promotion_history.json")
RECENT_SHIRT_COOLDOWN = 12
RECENT_THEME_WINDOW = 12


def load_history(path=DEFAULT_HISTORY_PATH):
    history_path = Path(path)
    if not history_path.exists():
        return []

    with history_path.open() as handle:
        history = json.load(handle)

    return history if isinstance(history, list) else []


def select_shirts(inventory, history, count):
    if count <= 0:
        return []

    eligible = [
        shirt
        for shirt in inventory
        if shirt.get("status") == "available"
        and shirt.get("is_promotable", True)
        and shirt.get("promotion_status") != "skip"
    ]
    if not eligible:
        return []

    recency_map = build_recency_map(history)
    recent_shirt_ids = build_recent_shirt_ids(history, RECENT_SHIRT_COOLDOWN)
    recent_theme_counts = build_recent_theme_counts(history, eligible, RECENT_THEME_WINDOW)
    ranked = sorted(
        eligible,
        key=lambda shirt: (
            shirt["shirt_id"] in recent_shirt_ids,
            recent_theme_counts.get(normalize_theme(shirt.get("theme", "")), 0),
            recency_map.get(shirt["shirt_id"], -1),
            len(shirt.get("tags", [])),
            shirt["title"].lower(),
        ),
    )

    selected = []
    used_themes = set()
    for shirt in ranked:
        theme = shirt.get("theme", "")
        if theme and theme in used_themes and len(selected) < count:
            continue
        selected.append(shirt)
        if theme:
            used_themes.add(theme)
        if len(selected) == count:
            return selected

    for shirt in ranked:
        if shirt in selected:
            continue
        selected.append(shirt)
        if len(selected) == count:
            break

    return selected


def append_history(entries, path=DEFAULT_HISTORY_PATH):
    history = load_history(path)
    history.extend(entries)
    history_path = Path(path)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("w") as handle:
        json.dump(history, handle, indent=2)
        handle.write("\n")


def build_recency_map(history):
    recency_map = {}
    for index, entry in enumerate(history):
        shirt_id = entry.get("shirt_id")
        if shirt_id:
            recency_map[shirt_id] = index
    return recency_map


def build_recent_shirt_ids(history, limit):
    recent = []
    for entry in reversed(history):
        shirt_id = str(entry.get("shirt_id") or "").strip()
        if shirt_id and shirt_id not in recent:
            recent.append(shirt_id)
        if len(recent) == limit:
            break
    return set(recent)


def build_recent_theme_counts(history, inventory, limit):
    inventory_by_id = {shirt["shirt_id"]: shirt for shirt in inventory}
    counts = {}
    seen_entries = 0
    for entry in reversed(history):
        shirt_id = str(entry.get("shirt_id") or "").strip()
        shirt = inventory_by_id.get(shirt_id)
        if not shirt:
            continue
        theme = normalize_theme(shirt.get("theme", ""))
        if theme:
            counts[theme] = counts.get(theme, 0) + 1
        seen_entries += 1
        if seen_entries == limit:
            break
    return counts


def normalize_theme(theme):
    return str(theme or "").strip().lower()
