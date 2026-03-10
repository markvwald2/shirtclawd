import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bot.inventory_sync import sync_inventory


class InventorySyncTests(unittest.TestCase):
    def test_sync_inventory_writes_destination_metadata_and_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            destination = root / "shirt_inventory.json"
            metadata_path = root / "inventory_metadata.json"
            snapshot_dir = root / "snapshots"
            payload = json.dumps(
                [
                    {
                        "shirt_id": "abc123",
                        "shirt_name": "Biblical Sense",
                        "product_url": "https://example.com",
                        "image_url": "https://example.com/image.jpg",
                    }
                ]
            )

            with patch("bot.inventory_sync.fetch_inventory_payload", return_value=payload):
                metadata = sync_inventory(
                    source_url="https://example.com/inventory.json",
                    destination=destination,
                    metadata_path=metadata_path,
                    snapshot_dir=snapshot_dir,
                )

            self.assertEqual(metadata["record_count"], 1)
            self.assertTrue(destination.exists())
            self.assertTrue(metadata_path.exists())
            self.assertEqual(json.loads(metadata_path.read_text())["source_url"], "https://example.com/inventory.json")
            self.assertTrue(Path(metadata["snapshot_path"]).exists())


if __name__ == "__main__":
    unittest.main()
