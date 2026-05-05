import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bot.instagram_publisher import (
    build_instagram_caption,
    create_comment_reply,
    ensure_link_in_bio_before_hashtags,
    load_posts,
    normalize_limit_response,
    publish_comment_reply,
    publish_post,
    resolve_post_image_urls,
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
        self.assertIn("Link in bio.", caption)

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
        self.assertIn("Link in bio.", caption)

    def test_build_instagram_caption_places_link_in_bio_before_hashtags(self):
        caption = ensure_link_in_bio_before_hashtags("Caption text\n\n#one #two")

        self.assertEqual(caption, "Caption text\n\nLink in bio.\n\n#one #two")

    def test_build_instagram_caption_does_not_duplicate_link_in_bio(self):
        caption = ensure_link_in_bio_before_hashtags("Caption text\n\nLink in bio.\n\n#one #two")

        self.assertEqual(caption.lower().count("link in bio"), 1)

    def test_resolve_post_image_urls_prefers_carousel_items(self):
        urls = resolve_post_image_urls(
            {
                "image_url": "https://example.com/one.jpg",
                "image_urls": ["https://example.com/two.jpg"],
                "carousel_items": [
                    {"image_url": "https://example.com/one.jpg"},
                    {"image_url": "https://example.com/two.jpg"},
                ],
            }
        )

        self.assertEqual(urls, ["https://example.com/one.jpg", "https://example.com/two.jpg"])

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

    def test_publish_post_uses_carousel_flow_for_multiple_images(self):
        post = {
            "shirt_id": "coloradans_against_set",
            "shirt_ids": ["1", "2"],
            "title": "Coloradans Against Shirt Line",
            "caption": "Pick your complaint.\n\n#ColoradansAgainst",
            "image_urls": ["https://example.com/one.jpg", "https://example.com/two.jpg"],
        }
        responses = [
            {"data": [{"quota_usage": 0, "config": {"quota_total": 25}}]},
            {"id": "child1"},
            {"status_code": "FINISHED"},
            {"id": "child2"},
            {"status_code": "FINISHED"},
            {"id": "carousel1"},
            {"status_code": "FINISHED"},
            {"id": "media123"},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "publish_log.jsonl"
            with patch("bot.instagram_publisher.api_request", side_effect=responses) as api_mock:
                result = publish_post(
                    post,
                    dry_run=False,
                    credentials={"access_token": "token", "account_id": "1784"},
                    log_path=log_path,
                )
            event = json.loads(log_path.read_text().strip())

        self.assertTrue(result["is_carousel"])
        self.assertEqual(result["instagram_media_id"], "media123")
        payloads = [call.kwargs["payload"] for call in api_mock.call_args_list]
        self.assertEqual(payloads[1]["is_carousel_item"], "true")
        self.assertEqual(payloads[3]["is_carousel_item"], "true")
        self.assertEqual(payloads[5]["media_type"], "CAROUSEL")
        self.assertEqual(payloads[5]["children"], "child1,child2")
        self.assertEqual(event["status"], "published_carousel")

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

    def test_create_comment_reply_posts_to_replies_edge(self):
        with patch("bot.instagram_publisher.api_request", return_value={"id": "reply123"}) as api_mock:
            response = create_comment_reply("comment123", "token", "Thanks")

        self.assertEqual(response["id"], "reply123")
        self.assertIn("/comment123/replies", api_mock.call_args.args[0])
        self.assertEqual(api_mock.call_args.kwargs["payload"]["message"], "Thanks")

    def test_publish_comment_reply_returns_instagram_comment_id(self):
        with patch("bot.instagram_publisher.api_request", return_value={"id": "reply123"}):
            with tempfile.TemporaryDirectory() as tmpdir:
                log_path = Path(tmpdir) / "publish_log.jsonl"
                result = publish_comment_reply(
                    "Thanks",
                    "comment123",
                    dry_run=False,
                    credentials={"access_token": "token", "account_id": "1784"},
                    log_path=log_path,
                )

        self.assertEqual(result["instagram_comment_id"], "reply123")
        self.assertEqual(result["target_comment_id"], "comment123")


if __name__ == "__main__":
    unittest.main()
