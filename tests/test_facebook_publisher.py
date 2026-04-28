import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bot.facebook_publisher import (
    build_facebook_link,
    build_facebook_message,
    create_object_comment,
    load_posts,
    publish_comment,
    publish_post,
    select_post,
)


TEST_LOG_PATH = Path("/tmp/facebook_publish_log_test.jsonl")


class FacebookPublisherTests(unittest.TestCase):
    def tearDown(self):
        if TEST_LOG_PATH.exists():
            TEST_LOG_PATH.unlink()

    def test_select_post_by_index(self):
        posts = [{"shirt_id": "1", "title": "One"}, {"shirt_id": "2", "title": "Two"}]
        post = select_post(posts, index=1)
        self.assertEqual(post["shirt_id"], "2")

    def test_build_facebook_message_prefers_caption(self):
        post = {
            "title": "Whip It",
            "headline": "Featured: Parking Violations: No Fun Allowed",
            "caption": "Channel your inner DEVO.",
            "url": "https://example.com/whip-it",
            "hashtags": ["#DEVO", "#NewWave"],
        }

        message = build_facebook_message(post)

        self.assertEqual(message, "Channel your inner DEVO.")

    def test_build_facebook_link_uses_post_url(self):
        post = {
            "title": "Whip It",
            "url": "https://www.thirdstringshirts.com/shirt/whip-it-123/index.html",
        }

        self.assertEqual(build_facebook_link(post), "https://www.thirdstringshirts.com/shirt/whip-it-123/index.html")

    def test_build_facebook_link_derives_canonical_product_page_from_hash_route(self):
        post = {
            "shirt_id": "5d89cbe26bbdbb2e6a46975e",
            "title": "Breaking Wind",
            "url": "https://www.thirdstringshirts.com/shop.html#!/breaking+wind?idea=5d89cbe26bbdbb2e6a46975e",
        }

        self.assertEqual(
            build_facebook_link(post),
            "https://www.thirdstringshirts.com/shirt/breaking-wind-5d89cbe26bbdbb2e6a46975e/index.html",
        )

    def test_publish_post_dry_run_logs_event(self):
        post = {
            "shirt_id": "abc123",
            "title": "Biblical Sense",
            "caption": "Caption text",
            "image_url": "https://example.com/image.jpg",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "publish_log.jsonl"
            result = publish_post(post, dry_run=True, log_path=log_path, page_id="page123")

            self.assertEqual(result["mode"], "dry_run")
            self.assertEqual(result["page_id"], "page123")
            lines = log_path.read_text().strip().splitlines()
            self.assertEqual(len(lines), 1)
            payload = json.loads(lines[0])
            self.assertEqual(payload["status"], "dry_run")
            self.assertEqual(payload["link"], "")

    def test_publish_post_uses_feed_endpoint_with_link(self):
        post = {
            "shirt_id": "abc123",
            "title": "Biblical Sense",
            "caption": "Caption text",
            "image_url": "https://example.com/image.jpg",
            "url": "https://example.com/product",
        }

        with patch("bot.facebook_publisher.api_request", return_value={"id": "post123"}) as api_mock:
            result = publish_post(
                post,
                dry_run=False,
                credentials={"access_token": "token", "page_id": "page123"},
                log_path=TEST_LOG_PATH,
            )

        self.assertEqual(result["facebook_post_id"], "post123")
        self.assertEqual(result["link"], "https://example.com/product")
        self.assertIn("/page123/feed", api_mock.call_args.args[0])

    def test_load_posts_reads_array(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "posts.json"
            path.write_text(json.dumps([{"shirt_id": "1"}]))
            posts = load_posts(path)
            self.assertEqual(len(posts), 1)

    def test_create_object_comment_posts_to_comments_edge(self):
        with patch("bot.facebook_publisher.api_request", return_value={"id": "comment123"}) as api_mock:
            response = create_object_comment("page123_post456", "token", "Reply text")

        self.assertEqual(response["id"], "comment123")
        self.assertIn("/page123_post456/comments", api_mock.call_args.args[0])
        self.assertEqual(api_mock.call_args.kwargs["payload"]["message"], "Reply text")

    def test_publish_comment_returns_facebook_comment_id(self):
        with patch("bot.facebook_publisher.api_request", return_value={"id": "comment123"}):
            result = publish_comment(
                "Reply text",
                "page123_post456",
                dry_run=False,
                credentials={"access_token": "token", "page_id": "page123"},
                log_path=TEST_LOG_PATH,
            )

        self.assertEqual(result["facebook_comment_id"], "comment123")
        self.assertEqual(result["target_object_id"], "page123_post456")


if __name__ == "__main__":
    unittest.main()
