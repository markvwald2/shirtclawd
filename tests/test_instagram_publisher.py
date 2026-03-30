import json
import tempfile
import unittest
from pathlib import Path

from bot.instagram_publisher import (
    build_instagram_caption,
    load_posts,
    normalize_limit_response,
    publish_post,
    select_post,
)


class InstagramPublisherTests(unittest.TestCase):
    def test_select_post_by_index(self):
        posts = [{"shirt_id": "1", "title": "One"}, {"shirt_id": "2", "title": "Two"}]
        post = select_post(posts, index=1)
        self.assertEqual(post["shirt_id"], "2")

    def test_build_instagram_caption_trims_long_caption(self):
        post = {
            "title": "Long Post",
            "headline": "A compact headline",
            "caption": "x" * 2300,
            "url": "https://example.com",
            "hashtags": ["#one", "#two"],
        }
        caption = build_instagram_caption(post)
        self.assertLessEqual(len(caption), 2200)

    def test_build_instagram_caption_strips_raw_urls(self):
        post = {
            "title": "Linked Post",
            "headline": "A compact headline",
            "caption": "Caption text https://example.com/product #tag",
            "url": "https://example.com/product",
            "hashtags": ["#one", "#two"],
        }

        caption = build_instagram_caption(post)

        self.assertNotIn("https://example.com/product", caption)

    def test_publish_post_dry_run_logs_event(self):
        post = {
            "shirt_id": "abc123",
            "title": "Biblical Sense",
            "caption": "Caption text https://example.com #tag",
            "image_url": "https://example.com/image.jpg",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "publish_log.jsonl"
            result = publish_post(post, dry_run=True, log_path=log_path, account_id="1784")

            self.assertEqual(result["mode"], "dry_run")
            self.assertEqual(result["account_id"], "1784")
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

    def test_normalize_limit_response_reads_data_payload(self):
        state = normalize_limit_response(
            {
                "data": [
                    {
                        "quota_usage": 24,
                        "config": {"quota_total": 25},
                    }
                ]
            }
        )

        self.assertEqual(state["quota_usage"], 24)
        self.assertEqual(state["quota_total"], 25)

    def test_normalize_limit_response_defaults_usage_to_zero(self):
        state = normalize_limit_response({"data": [{"config": {"quota_total": 25}}]})

        self.assertEqual(state["quota_usage"], 0)
        self.assertEqual(state["quota_total"], 25)


if __name__ == "__main__":
    unittest.main()
