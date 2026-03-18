import tempfile
import unittest
from pathlib import Path

from bot.approval_queue import approve_post, is_post_approved, load_approval_queue


class ApprovalQueueTests(unittest.TestCase):
    def test_approve_post_marks_post_as_approved(self):
        post = {"shirt_id": "abc123", "title": "Biblical Sense"}
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "queue.json"
            approve_post(post, "output/posts.json", "@3rdStringShirts", path=queue_path)

            self.assertTrue(
                is_post_approved(post, "output/posts.json", "@3rdStringShirts", path=queue_path)
            )
            queue = load_approval_queue(queue_path)
            self.assertEqual(len(queue["approved_posts"]), 1)

    def test_approve_post_tracks_platform_specific_entries(self):
        post = {"shirt_id": "abc123", "title": "Biblical Sense"}
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "queue.json"
            approve_post(post, "output/posts.json", "shirtclawd.bsky.social", path=queue_path, platform="bluesky")

            self.assertTrue(
                is_post_approved(
                    post,
                    "output/posts.json",
                    "shirtclawd.bsky.social",
                    path=queue_path,
                    platform="bluesky",
                )
            )
            self.assertFalse(
                is_post_approved(
                    post,
                    "output/posts.json",
                    "shirtclawd.bsky.social",
                    path=queue_path,
                    platform="x",
                )
            )
