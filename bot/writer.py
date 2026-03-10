import json
from pathlib import Path


def write_posts(posts, run_date, output_dir=Path("output"), platform="default"):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    destination = output_path / f"posts_{run_date}_{platform}.json"
    with destination.open("w") as handle:
        json.dump(posts, handle, indent=2)
        handle.write("\n")
    update_post_index(output_path, destination, posts, platform)
    return destination


def update_post_index(output_path, destination, posts, platform):
    index_path = output_path / "post_index.json"
    if index_path.exists():
        with index_path.open() as handle:
            index = json.load(handle)
    else:
        index = {"files": []}

    record = {
        "path": str(destination.relative_to(output_path.parent)),
        "filename": destination.name,
        "platform": platform,
        "post_count": len(posts),
        "titles": [post.get("title", "") for post in posts[:5]],
    }

    files = [entry for entry in index.get("files", []) if entry.get("filename") != destination.name]
    files.append(record)
    files.sort(key=lambda entry: entry["filename"], reverse=True)
    index["files"] = files[:50]

    with index_path.open("w") as handle:
        json.dump(index, handle, indent=2)
        handle.write("\n")
