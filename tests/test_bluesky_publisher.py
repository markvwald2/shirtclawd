import json
import tempfile
import unittest
from pathlib import Path

from bot.bluesky_publisher import build_bluesky_status, load_posts, publish_post, select_post


class BlueskyPublisherTests(unittest.TestCase):
    def test_select_post_by_index(self):
        posts = [{"shirt_id": "1", "title": "One"}, {"shirt_id": "2", "title": "Two"}]
        post = select_post(posts, index=1)
        self.assertEqual(post["shirt_id"], "2")

    def test_build_bluesky_status_trims_long_caption(self):
        post = {
            "title": "Long Post",
            "headline": "A compact headline",
            "caption": "x" * 500,
            "url": "https://example.com",
            "hashtags": ["#one", "#two"],
        }
        status = build_bluesky_status(post)
        self.assertLessEqual(len(status), 300)

    def test_publish_post_dry_run_logs_event(self):
        post = {
            "shirt_id": "abc123",
            "title": "Biblical Sense",
            "caption": "Caption text https://example.com #tag",
            "image_url": "https://example.com/image.jpg",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "publish_log.jsonl"
            result = publish_post(post, dry_run=True, log_path=log_path, handle="shirtclawd.bsky.social")

            self.assertEqual(result["mode"], "dry_run")
            self.assertEqual(result["handle"], "shirtclawd.bsky.social")
            lines = log_path.read_text().strip().splitlines()
            self.assertEqual(len(lines), 1)
            payload = json.loads(lines[0])
            self.assertEqual(payload["status"], "dry_run")

    def test_load_posts_reads_array(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "posts.json"
            path.write_text(json.dumps([{"shirt_id": "1"}]))
            posts = load_posts(path)
            self.assertEqual(len(posts), 1)


if __name__ == "__main__":
    unittest.main()
