import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bot.bluesky_publisher import (
    MAX_BLOB_BYTES,
    build_bluesky_status,
    build_external_embed,
    load_posts,
    optimize_image_for_bluesky,
    publish_post,
    select_post,
)


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

    def test_build_bluesky_status_strips_raw_urls(self):
        post = {
            "title": "Linked Post",
            "headline": "A compact headline",
            "caption": "Caption text https://example.com/product #tag",
            "url": "https://example.com/product",
            "hashtags": ["#one", "#two"],
        }

        status = build_bluesky_status(post)

        self.assertNotIn("https://example.com/product", status)

    def test_build_external_embed_uses_post_url_and_blob(self):
        post = {
            "title": "Biblical Sense",
            "headline": "A compact headline",
            "caption": "Caption text https://example.com/product #tag",
            "url": "https://example.com/product",
        }

        embed = build_external_embed(post, blob={"$type": "blob"})

        self.assertEqual(embed["$type"], "app.bsky.embed.external")
        self.assertEqual(embed["external"]["uri"], "https://example.com/product")
        self.assertEqual(embed["external"]["thumb"], {"$type": "blob"})

    @patch("bot.bluesky_publisher.resize_image_with_sips")
    def test_optimize_image_for_bluesky_leaves_small_images_unchanged(self, resize_image_with_sips):
        original = b"x" * 100

        payload, mime_type = optimize_image_for_bluesky(original, "image/png", max_bytes=MAX_BLOB_BYTES)

        self.assertEqual(payload, original)
        self.assertEqual(mime_type, "image/png")
        resize_image_with_sips.assert_not_called()

    @patch("bot.bluesky_publisher.resize_image_with_sips")
    def test_optimize_image_for_bluesky_uses_resized_result_when_oversized(self, resize_image_with_sips):
        original = b"x" * (MAX_BLOB_BYTES + 10)
        resize_image_with_sips.return_value = (b"y" * 100, "image/jpeg")

        payload, mime_type = optimize_image_for_bluesky(original, "image/png", max_bytes=MAX_BLOB_BYTES)

        self.assertEqual(payload, b"y" * 100)
        self.assertEqual(mime_type, "image/jpeg")

    @patch("bot.bluesky_publisher.resize_image_with_sips")
    def test_optimize_image_for_bluesky_falls_back_when_resize_unavailable(self, resize_image_with_sips):
        original = b"x" * (MAX_BLOB_BYTES + 10)
        resize_image_with_sips.return_value = None

        payload, mime_type = optimize_image_for_bluesky(original, "image/png", max_bytes=MAX_BLOB_BYTES)

        self.assertEqual(payload, original)
        self.assertEqual(mime_type, "image/png")

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
