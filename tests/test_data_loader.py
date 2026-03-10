import json
import tempfile
import unittest
from pathlib import Path

from bot.data_loader import load_inventory


class DataLoaderTests(unittest.TestCase):
    def test_load_inventory_normalizes_live_schema(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inventory_path = Path(tmpdir) / "inventory.json"
            inventory_path.write_text(
                json.dumps(
                    [
                        {
                            "shirt_id": "abc123",
                            "shirt_name": "Biblical Sense",
                            "product_url": "https://example.com/biblical-sense",
                            "image_url": "https://example.com/biblical-sense.jpg",
                            "tags": ["religion", "funny"],
                            "theme": "religion",
                            "sub_theme": "Bible jokes",
                        }
                    ]
                )
            )

            loaded = load_inventory(inventory_path)

            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["title"], "Biblical Sense")
            self.assertEqual(loaded[0]["url"], "https://example.com/biblical-sense")
            self.assertEqual(loaded[0]["tags"], ["religion", "funny"])

    def test_load_inventory_deduplicates_by_shirt_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inventory_path = Path(tmpdir) / "inventory.json"
            inventory_path.write_text(
                json.dumps(
                    [
                        {
                            "shirt_id": "abc123",
                            "title": "One",
                            "url": "https://example.com/one",
                            "image_url": "https://example.com/one.jpg",
                        },
                        {
                            "shirt_id": "abc123",
                            "title": "Two",
                            "url": "https://example.com/two",
                            "image_url": "https://example.com/two.jpg",
                        },
                    ]
                )
            )

            loaded = load_inventory(inventory_path)

            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["title"], "One")


if __name__ == "__main__":
    unittest.main()
