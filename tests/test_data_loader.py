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

    def test_load_inventory_merges_local_annotations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inventory_path = Path(tmpdir) / "inventory.json"
            annotations_path = Path(tmpdir) / "annotations.json"
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
                        }
                    ]
                )
            )
            annotations_path.write_text(
                json.dumps(
                    {
                        "abc123": {
                            "is_promotable": False,
                            "promotion_status": "skip",
                            "reference_summary": "A dry Bible joke for church-camp adults.",
                            "target_audience": ["church humor", "wordplay fans"],
                            "tone": "edgy_snarky",
                            "tone_notes": "Dry and a little smug.",
                            "notes": "Skip broad audience campaigns.",
                        }
                    }
                )
            )

            loaded = load_inventory(inventory_path, annotations_path=annotations_path)

            self.assertFalse(loaded[0]["is_promotable"])
            self.assertEqual(loaded[0]["promotion_status"], "skip")
            self.assertEqual(loaded[0]["reference_summary"], "A dry Bible joke for church-camp adults.")
            self.assertEqual(loaded[0]["target_audience"], ["church humor", "wordplay fans"])
            self.assertEqual(loaded[0]["tone"], "edgy_snarky")
            self.assertEqual(loaded[0]["tone_notes"], "Dry and a little smug.")
            self.assertEqual(loaded[0]["notes"], "Skip broad audience campaigns.")

    def test_load_inventory_canonicalizes_spreadshop_urls_to_storefront_domain(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inventory_path = Path(tmpdir) / "inventory.json"
            inventory_path.write_text(
                json.dumps(
                    [
                        {
                            "shirt_id": "abc123",
                            "shirt_name": "Riggs & Murtaugh",
                            "product_url": "https://thirdstringshirts.myspreadshop.com/riggs+%26+murtaugh?idea=5d89cc2e13615160bf6edc74",
                            "image_url": "https://example.com/riggs.jpg",
                        }
                    ]
                )
            )

            loaded = load_inventory(inventory_path)

            self.assertEqual(
                loaded[0]["url"],
                "https://www.thirdstringshirts.com/shop.html#!/riggs+%26+murtaugh?idea=5d89cc2e13615160bf6edc74",
            )

    def test_load_inventory_canonicalizes_any_myspreadshop_hostname(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inventory_path = Path(tmpdir) / "inventory.json"
            inventory_path.write_text(
                json.dumps(
                    [
                        {
                            "shirt_id": "abc123",
                            "shirt_name": "Breaking Wind",
                            "product_url": "https://thirdstringshirts.myspreadshop.co.uk/breaking+wind?idea=5d89cbe26bbdbb2e6a46975e",
                            "image_url": "https://example.com/breaking-wind.jpg",
                        },
                        {
                            "shirt_id": "def456",
                            "shirt_name": "Biblical Sense",
                            "product_url": "https://foo.myspreadshop.com/biblical+sense?idea=5d8e1581b4b8c76220050334",
                            "image_url": "https://example.com/biblical-sense.jpg",
                        },
                    ]
                )
            )

            loaded = load_inventory(inventory_path)

            self.assertEqual(
                loaded[0]["url"],
                "https://www.thirdstringshirts.com/shop.html#!/breaking+wind?idea=5d89cbe26bbdbb2e6a46975e",
            )
            self.assertEqual(
                loaded[1]["url"],
                "https://www.thirdstringshirts.com/shop.html#!/biblical+sense?idea=5d8e1581b4b8c76220050334",
            )

    def test_load_inventory_defaults_unannotated_shirts_to_review_only(self):
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
                        }
                    ]
                )
            )

            loaded = load_inventory(inventory_path, annotations_path=Path(tmpdir) / "missing.json")

            self.assertFalse(loaded[0]["is_promotable"])
            self.assertEqual(loaded[0]["promotion_status"], "review")

    def test_load_inventory_canonicalizes_local_etsy_asset_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inventory_path = Path(tmpdir) / "inventory.json"
            inventory_path.write_text(
                json.dumps(
                    [
                        {
                            "shirt_id": "etsy_123",
                            "title": "Coloradans Against Hiking",
                            "url": "https://example.com/hiking",
                            "image_url": "./assets/etsy/unisex-tri-blend-t-shirt-athletic-grey-triblend-front-69ad833a66dfe.png",
                        }
                    ]
                )
            )

            loaded = load_inventory(inventory_path)

            self.assertEqual(
                loaded[0]["image_url"],
                "https://www.thirdstringshirts.com/assets/etsy/unisex-tri-blend-t-shirt-athletic-grey-triblend-front-69ad833a66dfe.png",
            )

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
