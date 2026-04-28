import json
import tempfile
import unittest
from pathlib import Path

from bot.follow_up import approve_follow_up_action, list_follow_up_actions
from bot.follow_up_session import (
    build_inbox_follow_up_actions,
    load_follow_up_session_state,
    run_follow_up_session,
)


class FollowUpSessionTests(unittest.TestCase):
    def test_build_inbox_follow_up_actions_creates_stable_reply_action(self):
        actions = build_inbox_follow_up_actions(
            "2026-04-26",
            [
                {
                    "reason": "reply",
                    "uri": "at://did:plc:abc/app.bsky.feed.post/3reply",
                    "reason_subject": "at://did:plc:me/app.bsky.feed.post/3root",
                    "author_handle": "denverpost.com",
                    "author_display_name": "The Denver Post",
                    "text": "Craft beer is civic infrastructure.",
                    "indexed_at": "2026-04-26T14:00:00Z",
                    "url": "https://bsky.app/profile/denverpost.com/post/3reply",
                }
            ],
            generated_at="2026-04-26T15:00:00+00:00",
        )

        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["action_id"], "FU-2026-04-26-IN-3reply")
        self.assertEqual(actions[0]["kind"], "reply_comment")
        self.assertEqual(actions[0]["platform"], "bluesky")
        self.assertEqual(actions[0]["target_url"], "https://bsky.app/profile/denverpost.com/post/3reply")
        self.assertIn("argument deserves merchandise", actions[0]["draft_text"])

    def test_run_follow_up_session_refreshes_queue_executes_approved_and_saves_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output_dir = root / "output"
            data_dir = root / "data"
            output_dir.mkdir()
            data_dir.mkdir()
            run_date = "2026-04-26"
            plan = {
                "plan_date": run_date,
                "campaign": "coloradans_against",
                "planned_posts": [
                    {
                        "slot": 1,
                        "platform": "bluesky",
                        "shirt_id": "shirt-1",
                        "title": "Coloradans Against Craft Beer",
                        "series": "Coloradans Against",
                        "content_goal": "conversation",
                        "cta_goal": "reply",
                    }
                ],
            }
            plan_path = output_dir / f"daily_plan_{run_date}.json"
            plan_path.write_text(json.dumps(plan))
            (output_dir / f"posts_{run_date}_bluesky.json").write_text(
                json.dumps(
                    [
                        {
                            "shirt_id": "shirt-1",
                            "title": "Coloradans Against Craft Beer",
                            "platform": "bluesky",
                            "campaign": "coloradans_against",
                            "content_goal": "conversation",
                            "cta_goal": "reply",
                        }
                    ]
                )
            )
            (data_dir / "bluesky_publish_log.jsonl").write_text(
                json.dumps(
                    {
                        "logged_at": "2026-04-26T13:00:00+00:00",
                        "status": "published",
                        "shirt_id": "shirt-1",
                        "title": "Coloradans Against Craft Beer",
                        "uri": "at://did:plc:me/app.bsky.feed.post/3root",
                    }
                )
                + "\n"
            )
            queue_path = data_dir / "follow_up_action_queue.json"
            state_path = data_dir / "follow_up_session_state.json"

            first = run_follow_up_session(
                run_date=run_date,
                plan_path=plan_path,
                output_dir=output_dir,
                log_dir=data_dir,
                queue_path=queue_path,
                state_path=state_path,
                skip_target_discovery=True,
                fetch_inbox_items_fn=lambda **_: [
                    {
                        "reason": "mention",
                        "uri": "at://did:plc:abc/app.bsky.feed.post/3mention",
                        "reason_subject": "at://did:plc:me/app.bsky.feed.post/3root",
                        "author_handle": "fan.example",
                        "author_display_name": "Fan Example",
                        "text": "Are you seeing this?",
                        "indexed_at": "2026-04-26T14:00:00Z",
                        "url": "https://bsky.app/profile/fan.example/post/3mention",
                    }
                ],
                now="2026-04-26T15:00:00+00:00",
            )

            self.assertEqual(first["inbox_action_count"], 1)
            approve_follow_up_action(
                "FU-2026-04-26-IN-3mention",
                approved_text="We have been summoned.",
                path=queue_path,
            )

            second = run_follow_up_session(
                run_date=run_date,
                plan_path=plan_path,
                output_dir=output_dir,
                log_dir=data_dir,
                queue_path=queue_path,
                state_path=state_path,
                skip_target_discovery=True,
                fetch_inbox_items_fn=lambda **_: [],
                execute_approved=True,
                publish=True,
                execute_approved_fn=lambda **_: [
                    {
                        "action_id": "FU-2026-04-26-IN-3mention",
                        "status": "sent",
                        "external_action_id": "at://did:plc:me/app.bsky.feed.post/3reply",
                    }
                ],
                now="2026-04-26T16:00:00+00:00",
            )

            state = load_follow_up_session_state(state_path)
            actions = list_follow_up_actions(queue_path, run_date=run_date)
            session_report_exists = Path(first["session_report_path"]).exists()

        self.assertTrue(session_report_exists)
        self.assertEqual(second["execution_sent_count"], 1)
        self.assertEqual(state["last_run_date"], run_date)
        self.assertTrue(any(action["action_id"] == "FU-2026-04-26-IN-3mention" for action in actions))

    def test_run_follow_up_session_automation_only_suppresses_manual_queue_items(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output_dir = root / "output"
            data_dir = root / "data"
            output_dir.mkdir()
            data_dir.mkdir()
            run_date = "2026-04-26"
            plan = {
                "plan_date": run_date,
                "campaign": "coloradans_against",
                "planned_posts": [
                    {
                        "slot": 1,
                        "platform": "facebook",
                        "shirt_id": "shirt-1",
                        "title": "Coloradans Against Triathlons",
                        "series": "Coloradans Against",
                        "content_goal": "conversation",
                        "cta_goal": "reply",
                    }
                ],
            }
            plan_path = output_dir / f"daily_plan_{run_date}.json"
            plan_path.write_text(json.dumps(plan))
            (output_dir / f"posts_{run_date}_facebook.json").write_text(json.dumps([plan["planned_posts"][0]]))
            queue_path = data_dir / "follow_up_action_queue.json"
            queue_path.write_text(
                json.dumps(
                    {
                        "actions": [
                            {
                                "action_id": "FU-2026-04-26-O1",
                                "date": run_date,
                                "kind": "outreach_dm",
                                "status": "approved",
                                "platform": "manual",
                                "draft_text": "Manual",
                                "approved_text": "Manual",
                                "created_at": "2026-04-26T14:00:00+00:00",
                                "updated_at": "2026-04-26T14:00:00+00:00",
                                "notes": [],
                            }
                        ]
                    }
                )
            )

            result = run_follow_up_session(
                run_date=run_date,
                plan_path=plan_path,
                output_dir=output_dir,
                log_dir=data_dir,
                queue_path=queue_path,
                state_path=data_dir / "follow_up_session_state.json",
                skip_target_discovery=True,
                fetch_inbox_items_fn=lambda **_: [],
                automation_only=True,
                now="2026-04-26T15:00:00+00:00",
            )
            actions = list_follow_up_actions(queue_path, run_date=run_date)

        self.assertEqual(actions, [])
        self.assertEqual(result["planned_action_count"], 0)
        self.assertGreater(result["suppressed_planned_action_count"], 0)


if __name__ == "__main__":
    unittest.main()
