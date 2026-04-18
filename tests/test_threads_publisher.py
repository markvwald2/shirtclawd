import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bot.threads_publisher import build_threads_status, load_posts, publish_post, select_post


class ThreadsPublisherTests(unittest.TestCase):
    def test_select_post_by_index(self):
        posts = [{"shirt_id": "1", "title": "One"}, {"shirt_id": "2", "title": "Two"}]
        post = select_post(posts, index=1)
        self.assertEqual(post["shirt_id"], "2")

    def test_build_threads_status_trims_long_caption(self):
        post = {
            "title": "Long Post",
            "headline": "A compact headline",
            "caption": "x" * 700,
            "url": "https://example.com",
            "hashtags": ["#one", "#two"],
        }
        status = build_threads_status(post)
        self.assertLessEqual(len(status), 500)

    def test_publish_post_dry_run_logs_event(self):
        post = {
            "shirt_id": "abc123",
            "title": "Biblical Sense",
            "caption": "Caption text https://example.com #tag",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "publish_log.jsonl"
            result = publish_post(post, dry_run=True, log_path=log_path, username="@3rdstringshirts")

            self.assertEqual(result["mode"], "dry_run")
            self.assertEqual(result["username"], "@3rdstringshirts")
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

    @patch("bot.threads_publisher.api_request")
    def test_publish_post_uses_image_container_when_image_url_is_present(self, api_request):
        api_request.side_effect = [{"id": "creation123"}, {"id": "thread456"}]
        post = {
            "shirt_id": "abc123",
            "title": "Biblical Sense",
            "caption": "Caption text",
            "image_url": "https://example.com/image.jpg",
            "alt_text": "Example alt text",
        }

        result = publish_post(
            post,
            dry_run=False,
            credentials={"access_token": "token", "user_id": "user123"},
            username="@3rdstringshirts",
        )

        self.assertEqual(result["threads_media_id"], "thread456")
        first_call = api_request.call_args_list[0]
        self.assertEqual(first_call.kwargs["payload"]["media_type"], "IMAGE")
        self.assertEqual(first_call.kwargs["payload"]["image_url"], "https://example.com/image.jpg")
        self.assertEqual(first_call.kwargs["payload"]["alt_text"], "Example alt text")


if __name__ == "__main__":
    unittest.main()
