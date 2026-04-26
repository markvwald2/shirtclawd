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

    def test_execute_approved_unsupported_platform_reports_without_sending(self):
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
                        "target_url": "https://example.com/post",
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

            self.assertEqual(results[0]["status"], "unsupported")
            self.assertIn("instagram", results[0]["reason"])


if __name__ == "__main__":
    unittest.main()
