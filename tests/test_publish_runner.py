import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bot.publish_runner import build_published_keys, load_publish_log, publish_approved_x_posts


class PublishRunnerTests(unittest.TestCase):
    def test_load_publish_log_reads_jsonl(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "x_publish_log.jsonl"
            log_path.write_text(
                json.dumps({"status": "published", "shirt_id": "1", "handle": "@3rdStringShirts"}) + "\n"
            )

            events = load_publish_log(log_path)

            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["shirt_id"], "1")

    def test_build_published_keys_only_tracks_published_events(self):
        keys = build_published_keys(
            [
                {"status": "published", "shirt_id": "1", "handle": "@3rdStringShirts"},
                {"status": "dry_run", "shirt_id": "2", "handle": "@3rdStringShirts"},
            ]
        )

        self.assertEqual(keys, {("1", "@3rdStringShirts")})

    def test_publish_approved_x_posts_skips_already_published_items(self):
        queue = {
            "approved_posts": [
                {
                    "shirt_id": "1",
                    "title": "Alpha",
                    "source_file": "output/posts_x.json",
                    "platform": "x",
                    "handle": "@3rdStringShirts",
                },
                {
                    "shirt_id": "2",
                    "title": "Beta",
                    "source_file": "output/posts_x.json",
                    "platform": "x",
                    "handle": "@3rdStringShirts",
                },
            ]
        }
        events = [{"status": "published", "shirt_id": "1", "handle": "@3rdStringShirts"}]
        posts = [{"shirt_id": "2", "title": "Beta", "caption": "hello", "image_url": "https://example.com/img.jpg"}]

        with patch("bot.publish_runner.load_approval_queue", return_value=queue), \
                patch("bot.publish_runner.load_publish_log", return_value=events), \
                patch("bot.publish_runner.load_posts", return_value=posts), \
                patch("bot.publish_runner.select_post", return_value=posts[0]), \
                patch("bot.publish_runner.publish_post", return_value={"status": "published", "shirt_id": "2"}) as publish_post:
            results = publish_approved_x_posts(dry_run=False)

        self.assertEqual(results, [{"status": "published", "shirt_id": "2"}])
        publish_post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
