import json
import tempfile
import unittest
from pathlib import Path

from bot.catalog_ops import CatalogError, add_inventory_shirt, upsert_shirt_annotation


class CatalogOpsTests(unittest.TestCase):
    def test_add_inventory_shirt_appends_manual_record(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inventory_path = Path(tmpdir) / "inventory.json"
            inventory_path.write_text("[]\n")

            record = add_inventory_shirt(
                shirt_id="abc123",
                title="Biblical Sense",
                product_url="https://example.com/biblical-sense",
                image_url="https://example.com/biblical-sense.jpg",
                tags=["religion, funny", "wordplay"],
                theme="religion",
                sub_theme="Bible jokes",
                inventory_path=inventory_path,
            )

            payload = json.loads(inventory_path.read_text())
            self.assertEqual(record["shirt_id"], "abc123")
            self.assertEqual(record["shirt_name"], "Biblical Sense")
            self.assertEqual(record["tags"], ["religion", "funny", "wordplay"])
            self.assertEqual(payload[0]["source_match"], "manual")

    def test_add_inventory_shirt_rejects_duplicate_shirt_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inventory_path = Path(tmpdir) / "inventory.json"
            inventory_path.write_text(json.dumps([{"shirt_id": "abc123"}]))

            with self.assertRaises(CatalogError):
                add_inventory_shirt(
                    shirt_id="abc123",
                    title="Duplicate",
                    product_url="https://example.com/duplicate",
                    image_url="https://example.com/duplicate.jpg",
                    inventory_path=inventory_path,
                )

    def test_upsert_shirt_annotation_marks_shirt_promotable(self):
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
                        }
                    ]
                )
            )

            annotation = upsert_shirt_annotation(
                shirt_id="abc123",
                reference_summary="A dry Bible joke for church-camp adults.",
                target_audience=["church humor", "wordplay fans"],
                tone="dry_wordplay",
                tone_notes="Keep it dry and lightly smug.",
                notes="Strong niche fit.",
                inventory_path=inventory_path,
                annotations_path=annotations_path,
            )

            payload = json.loads(annotations_path.read_text())
            self.assertTrue(annotation["is_promotable"])
            self.assertEqual(annotation["promotion_status"], "promote")
            self.assertEqual(payload["abc123"]["target_audience"], ["church humor", "wordplay fans"])

    def test_upsert_shirt_annotation_requires_existing_inventory_shirt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inventory_path = Path(tmpdir) / "inventory.json"
            inventory_path.write_text("[]\n")

            with self.assertRaises(CatalogError):
                upsert_shirt_annotation(
                    shirt_id="missing",
                    reference_summary="No inventory match.",
                    inventory_path=inventory_path,
                    annotations_path=Path(tmpdir) / "annotations.json",
                )


if __name__ == "__main__":
    unittest.main()
