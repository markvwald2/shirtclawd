import json
import tempfile
import unittest
from pathlib import Path

from bot.writer import write_posts


class WriterTests(unittest.TestCase):
    def test_write_posts_uses_run_id_in_filename_and_keeps_both_runs(self):
        posts = [
            {
                "shirt_id": "shirt-1",
                "title": "Test Shirt",
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"

            first = write_posts(
                posts,
                "2026-04-05",
                output_dir=output_dir,
                platform="instagram",
                run_id="run_20260405T010203Z_aaaabbbb",
            )
            second = write_posts(
                posts,
                "2026-04-05",
                output_dir=output_dir,
                platform="instagram",
                run_id="run_20260405T020304Z_ccccdddd",
            )

            self.assertEqual(first.name, "posts_2026-04-05_instagram_20260405T010203Z_aaaabbbb.json")
            self.assertEqual(second.name, "posts_2026-04-05_instagram_20260405T020304Z_ccccdddd.json")
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())

            index = json.loads((output_dir / "post_index.json").read_text())
            instagram_entries = [entry for entry in index["files"] if entry["platform"] == "instagram"]

            self.assertEqual(len(instagram_entries), 2)
            self.assertEqual(instagram_entries[0]["filename"], second.name)
            self.assertEqual(instagram_entries[0]["run_id"], "run_20260405T020304Z_ccccdddd")
            self.assertEqual(instagram_entries[1]["filename"], first.name)
            self.assertEqual(instagram_entries[1]["run_id"], "run_20260405T010203Z_aaaabbbb")


if __name__ == "__main__":
    unittest.main()
