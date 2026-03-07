# Shirt Inventory

Minimal repo contents:

- `shirt_inventory.json`: Canonical inventory and metadata dataset.
- `shirt-inventory-viewer.hmtl`: Local editor/viewer for the dataset.

## Use

Start a local server from this directory:

```bash
python3 -m http.server 8000
```

Open:

- `http://localhost:8000/shirt-inventory-viewer.hmtl`

Use **Export JSON** in the viewer to download updated inventory after edits.
