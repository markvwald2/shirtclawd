import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bot.threads_publisher import (
    build_threads_status,
    create_carousel_container,
    create_carousel_item_container,
    create_container,
    load_posts,
    publish_post,
    publish_reply,
    resolve_post_media_items,
    select_post,
)


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

    def test_resolve_post_media_items_reads_carousel_items(self):
        items = resolve_post_media_items(
            {
                "image_url": "https://example.com/one.jpg",
                "carousel_items": [
                    {"image_url": "https://example.com/one.jpg", "alt_text": "One"},
                    {"image_url": "https://example.com/two.jpg", "alt_text": "Two"},
                ],
            }
        )

        self.assertEqual([item["image_url"] for item in items], ["https://example.com/one.jpg", "https://example.com/two.jpg"])
        self.assertEqual(items[1]["alt_text"], "Two")

    @patch("bot.threads_publisher.load_inventory")
    @patch("bot.threads_publisher.api_request")
    def test_publish_post_recovers_missing_image_url_from_inventory(self, api_request, load_inventory):
        api_request.side_effect = [{"id": "creation123"}, {"id": "thread456"}]
        load_inventory.return_value = [
            {
                "shirt_id": "abc123",
                "url": "https://example.com/product",
                "image_url": "https://example.com/recovered.jpg",
            }
        ]
        post = {
            "shirt_id": "abc123",
            "title": "Biblical Sense",
            "caption": "Caption text",
            "image_url": "",
            "url": "https://example.com/product",
            "alt_text": "Example alt text",
        }

        result = publish_post(
            post,
            dry_run=False,
            credentials={"access_token": "token", "user_id": "user123"},
            username="@3rdstringshirts",
        )

        self.assertEqual(result["image_url"], "https://example.com/recovered.jpg")
        first_call = api_request.call_args_list[0]
        self.assertEqual(first_call.kwargs["payload"]["media_type"], "IMAGE")
        self.assertEqual(first_call.kwargs["payload"]["image_url"], "https://example.com/recovered.jpg")

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

    @patch("bot.threads_publisher.api_request")
    def test_create_container_can_target_reply(self, api_request):
        api_request.return_value = {"id": "creation123"}

        create_container("user123", "token", "Reply text", reply_to_id="thread123")

        self.assertEqual(api_request.call_args.kwargs["payload"]["reply_to_id"], "thread123")
        self.assertEqual(api_request.call_args.kwargs["payload"]["media_type"], "TEXT")

    @patch("bot.threads_publisher.api_request")
    def test_create_carousel_item_container_marks_item(self, api_request):
        api_request.return_value = {"id": "child1"}

        creation_id = create_carousel_item_container("user123", "token", "https://example.com/one.jpg", alt_text="One")

        self.assertEqual(creation_id, "child1")
        payload = api_request.call_args.kwargs["payload"]
        self.assertEqual(payload["media_type"], "IMAGE")
        self.assertEqual(payload["is_carousel_item"], "true")
        self.assertEqual(payload["alt_text"], "One")

    @patch("bot.threads_publisher.api_request")
    def test_create_carousel_container_joins_children(self, api_request):
        api_request.return_value = {"id": "carousel1"}

        creation_id = create_carousel_container("user123", "token", "Caption", ["child1", "child2"])

        self.assertEqual(creation_id, "carousel1")
        payload = api_request.call_args.kwargs["payload"]
        self.assertEqual(payload["media_type"], "CAROUSEL")
        self.assertEqual(payload["children"], "child1,child2")
        self.assertEqual(payload["text"], "Caption")

    @patch("bot.threads_publisher.api_request")
    def test_publish_post_uses_carousel_flow_for_multiple_images(self, api_request):
        api_request.side_effect = [{"id": "child1"}, {"id": "child2"}, {"id": "carousel1"}, {"id": "thread456"}]
        post = {
            "shirt_id": "coloradans_against_set",
            "shirt_ids": ["1", "2"],
            "title": "Coloradans Against Shirt Line",
            "caption": "Pick your complaint.",
            "image_urls": ["https://example.com/one.jpg", "https://example.com/two.jpg"],
        }

        result = publish_post(
            post,
            dry_run=False,
            credentials={"access_token": "token", "user_id": "user123"},
            username="@3rdstringshirts",
        )

        self.assertTrue(result["is_carousel"])
        self.assertEqual(result["child_creation_ids"], ["child1", "child2"])
        self.assertEqual(result["threads_media_id"], "thread456")
        self.assertEqual(api_request.call_args_list[2].kwargs["payload"]["media_type"], "CAROUSEL")

    @patch("bot.threads_publisher.api_request")
    def test_publish_reply_creates_and_publishes_reply_container(self, api_request):
        api_request.side_effect = [{"id": "creation123"}, {"id": "thread456"}]
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "publish_log.jsonl"
            result = publish_reply(
                "Reply text",
                "target123",
                dry_run=False,
                credentials={"access_token": "token", "user_id": "user123"},
                log_path=log_path,
                username="@3rdstringshirts",
            )

        self.assertEqual(result["threads_media_id"], "thread456")
        self.assertEqual(api_request.call_args_list[0].kwargs["payload"]["reply_to_id"], "target123")


if __name__ == "__main__":
    unittest.main()
