import json
import tempfile
import unittest
from pathlib import Path

from bot.facebook_discovery import facebook_search_url, find_reply_candidates, load_targets


class FacebookDiscoveryTests(unittest.TestCase):
    def test_find_reply_candidates_returns_curated_targets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            targets_path = Path(tmpdir) / "targets.json"
            targets_path.write_text(
                json.dumps(
                    [
                        {
                            "name": "Denver Beer Page",
                            "url": "https://www.facebook.com/denverbeer",
                            "keywords": ["denver", "beer", "brewery"],
                            "notes": "Denver beer conversations.",
                        },
                        {
                            "name": "Unrelated Page",
                            "url": "https://www.facebook.com/unrelated",
                            "keywords": ["knitting"],
                            "notes": "Not relevant.",
                        },
                    ]
                )
            )

            candidates = find_reply_candidates(
                ["Denver craft beer"],
                topic="craft beer",
                max_candidates=2,
                targets_path=targets_path,
            )

        self.assertEqual(candidates[0]["author_display_name"], "Denver Beer Page")
        self.assertEqual(candidates[0]["url"], "https://www.facebook.com/denverbeer")
        self.assertTrue(candidates[0]["manual_review"])
        self.assertIn("Search link", candidates[0]["reason"])

    def test_load_targets_falls_back_to_defaults_for_missing_file(self):
        targets = load_targets(Path("/tmp/does-not-exist-facebook-targets.json"))

        self.assertTrue(targets)

    def test_facebook_search_url_encodes_query(self):
        self.assertEqual(
            facebook_search_url("Denver craft beer"),
            "https://www.facebook.com/search/posts/?q=Denver+craft+beer",
        )


if __name__ == "__main__":
    unittest.main()
