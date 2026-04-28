import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bot.follow_up import approve_follow_up_action, list_follow_up_actions, merge_follow_up_actions
from bot.follow_up_executor import execute_approved_actions


class FollowUpExecutorTests(unittest.TestCase):
    def test_execute_approved_bluesky_action_dry_run_does_not_mark_sent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "queue.json"
            log_path = Path(tmpdir) / "execution.jsonl"
            merge_follow_up_actions(
                [
                    {
                        "action_id": "FU-2026-04-26-01-R1",
                        "date": "2026-04-26",
                        "kind": "reply_comment",
                        "status": "drafted",
                        "platform": "bluesky",
                        "target_url": "",
                        "draft_text": "Draft",
                        "approved_text": "",
                        "created_at": "2026-04-26T14:00:00+00:00",
                        "updated_at": "2026-04-26T14:00:00+00:00",
                        "notes": [],
                    }
                ],
                path=queue_path,
            )
            approve_follow_up_action(
                "FU-2026-04-26-01-R1",
                approved_text="Final",
                target_url="at://did:plc:abc/app.bsky.feed.post/3kabc",
                path=queue_path,
            )

            with patch(
                "bot.follow_up_executor.publish_bluesky_reply",
                return_value={"mode": "dry_run", "target": "at://did:plc:abc/app.bsky.feed.post/3kabc"},
            ) as publish_reply:
                results = execute_approved_actions(
                    queue_path=queue_path,
                    dry_run=True,
                    execution_log_path=log_path,
                )

            self.assertEqual(results[0]["status"], "dry_run")
            publish_reply.assert_called_once()
            actions = list_follow_up_actions(queue_path)
            self.assertEqual(actions[0]["status"], "approved")
            event = json.loads(log_path.read_text().strip())
            self.assertEqual(event["action_id"], "FU-2026-04-26-01-R1")

    def test_execute_approved_bluesky_action_publish_marks_sent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "queue.json"
            log_path = Path(tmpdir) / "execution.jsonl"
            merge_follow_up_actions(
                [
                    {
                        "action_id": "FU-2026-04-26-01-R1",
                        "date": "2026-04-26",
                        "kind": "reply_comment",
                        "status": "drafted",
                        "platform": "bluesky",
                        "target_url": "",
                        "draft_text": "Draft",
                        "approved_text": "",
                        "created_at": "2026-04-26T14:00:00+00:00",
                        "updated_at": "2026-04-26T14:00:00+00:00",
                        "notes": [],
                    }
                ],
                path=queue_path,
            )
            approve_follow_up_action(
                "FU-2026-04-26-01-R1",
                approved_text="Final",
                target_url="at://did:plc:abc/app.bsky.feed.post/3kabc",
                path=queue_path,
            )

            with patch(
                "bot.follow_up_executor.publish_bluesky_reply",
                return_value={"mode": "publish", "uri": "at://did:plc:me/app.bsky.feed.post/reply"},
            ):
                results = execute_approved_actions(
                    queue_path=queue_path,
                    dry_run=False,
                    execution_log_path=log_path,
                )

            self.assertEqual(results[0]["status"], "sent")
            sent_actions = list_follow_up_actions(queue_path, status="sent")
            self.assertEqual(sent_actions[0]["external_action_id"], "at://did:plc:me/app.bsky.feed.post/reply")

    def test_execute_approved_can_filter_by_run_date(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "queue.json"
            log_path = Path(tmpdir) / "execution.jsonl"
            merge_follow_up_actions(
                [
                    {
                        "action_id": "FU-2026-04-25-01-R1",
                        "date": "2026-04-25",
                        "kind": "reply_comment",
                        "status": "drafted",
                        "platform": "bluesky",
                        "target_url": "at://did:plc:abc/app.bsky.feed.post/old",
                        "draft_text": "Old",
                        "approved_text": "",
                        "created_at": "2026-04-25T14:00:00+00:00",
                        "updated_at": "2026-04-25T14:00:00+00:00",
                        "notes": [],
                    },
                    {
                        "action_id": "FU-2026-04-26-01-R1",
                        "date": "2026-04-26",
                        "kind": "reply_comment",
                        "status": "drafted",
                        "platform": "bluesky",
                        "target_url": "at://did:plc:abc/app.bsky.feed.post/new",
                        "draft_text": "New",
                        "approved_text": "",
                        "created_at": "2026-04-26T14:00:00+00:00",
                        "updated_at": "2026-04-26T14:00:00+00:00",
                        "notes": [],
                    },
                ],
                path=queue_path,
            )
            approve_follow_up_action("FU-2026-04-25-01-R1", path=queue_path)
            approve_follow_up_action("FU-2026-04-26-01-R1", path=queue_path)

            with patch(
                "bot.follow_up_executor.publish_bluesky_reply",
                return_value={"mode": "dry_run", "uri": "reply"},
            ) as publish_reply:
                results = execute_approved_actions(
                    queue_path=queue_path,
                    dry_run=True,
                    execution_log_path=log_path,
                    run_date="2026-04-26",
                )

            self.assertEqual([result["action_id"] for result in results], ["FU-2026-04-26-01-R1"])
            publish_reply.assert_called_once()

    def test_execute_approved_threads_action_publish_marks_sent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "queue.json"
            log_path = Path(tmpdir) / "execution.jsonl"
            merge_follow_up_actions(
                [
                    {
                        "action_id": "FU-2026-04-26-04-R1",
                        "date": "2026-04-26",
                        "kind": "reply_comment",
                        "status": "drafted",
                        "platform": "threads",
                        "target_thread_id": "thread123",
                        "target_url": "https://www.threads.net/@example/post/abc",
                        "draft_text": "Draft",
                        "approved_text": "",
                        "created_at": "2026-04-26T14:00:00+00:00",
                        "updated_at": "2026-04-26T14:00:00+00:00",
                        "notes": [],
                    }
                ],
                path=queue_path,
            )
            approve_follow_up_action("FU-2026-04-26-04-R1", path=queue_path)

            with patch(
                "bot.follow_up_executor.publish_threads_reply",
                return_value={"mode": "publish", "threads_media_id": "thread456"},
            ):
                results = execute_approved_actions(
                    queue_path=queue_path,
                    dry_run=False,
                    execution_log_path=log_path,
                )

            self.assertEqual(results[0]["status"], "sent")
            sent_actions = list_follow_up_actions(queue_path, status="sent")
            self.assertEqual(sent_actions[0]["external_action_id"], "thread456")

    def test_execute_approved_facebook_action_publish_marks_sent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "queue.json"
            log_path = Path(tmpdir) / "execution.jsonl"
            merge_follow_up_actions(
                [
                    {
                        "action_id": "FU-2026-04-26-03-R1",
                        "date": "2026-04-26",
                        "kind": "reply_comment",
                        "status": "drafted",
                        "platform": "facebook",
                        "target_object_id": "page123_post456",
                        "target_url": "https://www.facebook.com/example/posts/post456",
                        "draft_text": "Draft",
                        "approved_text": "",
                        "created_at": "2026-04-26T14:00:00+00:00",
                        "updated_at": "2026-04-26T14:00:00+00:00",
                        "notes": [],
                    }
                ],
                path=queue_path,
            )
            approve_follow_up_action("FU-2026-04-26-03-R1", path=queue_path)

            with patch(
                "bot.follow_up_executor.publish_facebook_comment",
                return_value={"mode": "publish", "facebook_comment_id": "comment123"},
            ):
                results = execute_approved_actions(
                    queue_path=queue_path,
                    dry_run=False,
                    execution_log_path=log_path,
                )

            self.assertEqual(results[0]["status"], "sent")
            sent_actions = list_follow_up_actions(queue_path, status="sent")
            self.assertEqual(sent_actions[0]["external_action_id"], "comment123")

    def test_execute_approved_instagram_action_without_comment_id_requires_manual(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "queue.json"
            log_path = Path(tmpdir) / "execution.jsonl"
            merge_follow_up_actions(
                [
                    {
                        "action_id": "FU-2026-04-26-02-R1",
                        "date": "2026-04-26",
                        "kind": "reply_comment",
                        "status": "drafted",
                        "platform": "instagram",
                        "target_url": "https://www.instagram.com/explore/tags/coloradohiking/",
                        "draft_text": "Draft",
                        "approved_text": "",
                        "created_at": "2026-04-26T14:00:00+00:00",
                        "updated_at": "2026-04-26T14:00:00+00:00",
                        "notes": [],
                    }
                ],
                path=queue_path,
            )
            approve_follow_up_action("FU-2026-04-26-02-R1", path=queue_path)

            results = execute_approved_actions(
                queue_path=queue_path,
                dry_run=False,
                execution_log_path=log_path,
            )

            self.assertEqual(results[0]["status"], "manual_required")
            self.assertIn("IG comment ID", results[0]["reason"])
            actions = list_follow_up_actions(queue_path)
            self.assertEqual(actions[0]["status"], "approved")

    def test_execute_approved_instagram_comment_reply_publish_marks_sent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "queue.json"
            log_path = Path(tmpdir) / "execution.jsonl"
            merge_follow_up_actions(
                [
                    {
                        "action_id": "FU-2026-04-26-IN-comment123",
                        "date": "2026-04-26",
                        "kind": "reply_comment",
                        "status": "drafted",
                        "platform": "instagram",
                        "target_comment_id": "comment123",
                        "target_url": "https://www.instagram.com/p/example/",
                        "draft_text": "Draft",
                        "approved_text": "",
                        "created_at": "2026-04-26T14:00:00+00:00",
                        "updated_at": "2026-04-26T14:00:00+00:00",
                        "notes": [],
                    }
                ],
                path=queue_path,
            )
            approve_follow_up_action("FU-2026-04-26-IN-comment123", path=queue_path)

            with patch(
                "bot.follow_up_executor.publish_instagram_comment_reply",
                return_value={"mode": "publish", "instagram_comment_id": "reply123"},
            ):
                results = execute_approved_actions(
                    queue_path=queue_path,
                    dry_run=False,
                    execution_log_path=log_path,
                )

            self.assertEqual(results[0]["status"], "sent")
            sent_actions = list_follow_up_actions(queue_path, status="sent")
            self.assertEqual(sent_actions[0]["external_action_id"], "reply123")

    def test_execute_approved_outreach_dm_requires_manual(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "queue.json"
            log_path = Path(tmpdir) / "execution.jsonl"
            merge_follow_up_actions(
                [
                    {
                        "action_id": "FU-2026-04-26-O1",
                        "date": "2026-04-26",
                        "kind": "outreach_dm",
                        "status": "drafted",
                        "platform": "manual",
                        "target_url": "",
                        "draft_text": "Draft",
                        "approved_text": "",
                        "created_at": "2026-04-26T14:00:00+00:00",
                        "updated_at": "2026-04-26T14:00:00+00:00",
                        "notes": [],
                    }
                ],
                path=queue_path,
            )
            approve_follow_up_action("FU-2026-04-26-O1", path=queue_path)

            results = execute_approved_actions(
                queue_path=queue_path,
                dry_run=False,
                execution_log_path=log_path,
            )

            self.assertEqual(results[0]["status"], "manual_required")
            self.assertIn("Outreach DMs", results[0]["reason"])


if __name__ == "__main__":
    unittest.main()
