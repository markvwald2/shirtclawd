import json
import tempfile
import unittest
from pathlib import Path

from bot.follow_up import (
    approve_follow_up_action,
    build_follow_up_actions,
    build_follow_up_brief,
    list_follow_up_actions,
    load_follow_up_queue,
    load_posts_for_plan,
    load_publish_records,
    mark_follow_up_action_sent,
    merge_follow_up_actions,
    skip_follow_up_action,
    write_follow_up_brief,
)


class FollowUpTests(unittest.TestCase):
    def test_build_follow_up_brief_uses_posts_and_publish_records(self):
        plan = {
            "plan_date": "2026-04-26",
            "campaign": "coloradans_against",
            "planned_posts": [
                {
                    "slot": 1,
                    "platform": "bluesky",
                    "shirt_id": "shirt-1",
                    "title": "Coloradans Against Craft Beer",
                    "series": "Coloradans Against",
                    "audience_lane": "colorado_regional_sarcasm",
                    "content_goal": "conversation",
                    "content_format": "group_chat_argument",
                    "cta_goal": "reply",
                    "active_offer": "25% off Coloradans Against shirts",
                    "offer_ends_on": "2026-04-29",
                },
                {
                    "slot": 2,
                    "platform": "instagram",
                    "shirt_id": "shirt-2",
                    "title": "Coloradans Against Hiking",
                    "series": "Coloradans Against",
                    "audience_lane": "colorado_regional_sarcasm",
                    "content_goal": "conversation",
                    "content_format": "pick_your_enemy",
                    "cta_goal": "share",
                },
            ],
        }
        post_refs = [
            {
                "entry": plan["planned_posts"][0],
                "post": {
                    "shirt_id": "shirt-1",
                    "title": "Coloradans Against Craft Beer",
                    "platform": "bluesky",
                    "content_goal": "conversation",
                    "cta_goal": "reply",
                    "caption": "Draft text",
                },
                "source_file": "output/posts_2026-04-26_bluesky.json",
            },
            {
                "entry": plan["planned_posts"][1],
                "post": {
                    "shirt_id": "shirt-2",
                    "title": "Coloradans Against Hiking",
                    "platform": "instagram",
                    "content_goal": "conversation",
                    "cta_goal": "share",
                    "caption": "Draft text",
                },
                "source_file": "output/posts_2026-04-26_instagram.json",
            },
        ]
        publish_records = [
            {
                "platform": "bluesky",
                "status": "published",
                "shirt_id": "shirt-1",
                "title": "Coloradans Against Craft Beer",
                "uri": "at://example/post/1",
            },
            {
                "platform": "instagram",
                "status": "published",
                "shirt_id": "shirt-2",
                "title": "Coloradans Against Hiking",
                "instagram_media_id": "ig-123",
            },
        ]

        brief = build_follow_up_brief(
            plan=plan,
            post_refs=post_refs,
            publish_records=publish_records,
            run_date="2026-04-26",
            uptime_minutes=60,
            generated_at="2026-04-26T14:00:00+00:00",
        )

        self.assertIn("# ShirtClawd Follow-Up Brief - 2026-04-26", brief)
        self.assertIn("Mode: semi-automated drafts and checklist only", brief)
        self.assertIn("at://example/post/1", brief)
        self.assertIn("ig-123", brief)
        self.assertIn("Colorado craft beer overrated", brief)
        self.assertIn("Reply And Comment Drafts", brief)
        self.assertIn("`FU-2026-04-26-01-R1` [drafted]", brief)
        self.assertIn("`FU-2026-04-26-O1`", brief)
        self.assertIn("Creator And Community Outreach", brief)
        self.assertIn("Performance Tracking", brief)

    def test_build_follow_up_actions_creates_reply_and_outreach_actions(self):
        plan = {
            "plan_date": "2026-04-26",
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
        post_refs = [
            {
                "entry": plan["planned_posts"][0],
                "post": plan["planned_posts"][0],
                "source_file": "output/posts.json",
            }
        ]
        publish_records = [
            {
                "platform": "bluesky",
                "status": "published",
                "shirt_id": "shirt-1",
                "uri": "at://example/post/1",
            }
        ]

        actions = build_follow_up_actions(
            plan,
            post_refs,
            publish_records,
            run_date="2026-04-26",
            generated_at="2026-04-26T14:00:00+00:00",
            target_discovery={
                "FU-2026-04-26-01": {
                    "candidates": [
                        {
                            "url": "https://bsky.app/profile/denverpost.com/post/3fresh",
                            "uri": "at://did:plc:abc/app.bsky.feed.post/3fresh",
                            "author_handle": "denverpost.com",
                            "author_display_name": "The Denver Post",
                            "query": "Colorado craft beer",
                            "reason": "Fresh post matching `Colorado craft beer`.",
                            "created_at": "2026-04-25T10:44:11+00:00",
                            "score": 72.5,
                            "like_count": 3,
                            "repost_count": 1,
                            "reply_count": 0,
                            "quote_count": 0,
                        }
                    ]
                }
            },
        )

        self.assertEqual(len(actions), 6)
        self.assertEqual(actions[0]["action_id"], "FU-2026-04-26-01-R1")
        self.assertEqual(actions[0]["kind"], "reply_comment")
        self.assertEqual(actions[0]["status"], "drafted")
        self.assertEqual(actions[0]["published_id"], "at://example/post/1")
        self.assertEqual(actions[0]["target_url"], "https://bsky.app/profile/denverpost.com/post/3fresh")
        self.assertEqual(actions[0]["target_author_handle"], "denverpost.com")
        self.assertEqual(actions[0]["target_metrics"]["likes"], 3)
        self.assertEqual(actions[-1]["action_id"], "FU-2026-04-26-O3")
        self.assertEqual(actions[-1]["kind"], "outreach_dm")

    def test_follow_up_queue_approves_sends_skips_and_preserves_status_on_merge(self):
        actions = [
            {
                "action_id": "FU-2026-04-26-01-R1",
                "date": "2026-04-26",
                "kind": "reply_comment",
                "status": "drafted",
                "draft_text": "Draft",
                "approved_text": "",
                "created_at": "2026-04-26T14:00:00+00:00",
                "updated_at": "2026-04-26T14:00:00+00:00",
                "notes": [],
            },
            {
                "action_id": "FU-2026-04-26-O1",
                "date": "2026-04-26",
                "kind": "outreach_dm",
                "status": "drafted",
                "draft_text": "Outreach",
                "approved_text": "",
                "created_at": "2026-04-26T14:00:00+00:00",
                "updated_at": "2026-04-26T14:00:00+00:00",
                "notes": [],
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "follow_up_action_queue.json"

            merge_follow_up_actions(actions, path=queue_path)
            approved = approve_follow_up_action(
                "FU-2026-04-26-01-R1",
                approved_text="Final copy",
                target_url="https://example.com/post",
                note="Looks good",
                path=queue_path,
            )
            self.assertEqual(approved["status"], "approved")
            self.assertEqual(approved["approved_text"], "Final copy")
            self.assertEqual(approved["target_url"], "https://example.com/post")
            self.assertEqual(len(approved["notes"]), 1)

            sent = mark_follow_up_action_sent(
                "FU-2026-04-26-01-R1",
                external_action_id="reply-123",
                path=queue_path,
            )
            self.assertEqual(sent["status"], "sent")
            self.assertEqual(sent["external_action_id"], "reply-123")

            skipped = skip_follow_up_action("FU-2026-04-26-O1", note="Bad fit", path=queue_path)
            self.assertEqual(skipped["status"], "skipped")

            merge_follow_up_actions(actions, path=queue_path)
            sent_actions = list_follow_up_actions(queue_path, run_date="2026-04-26", status="sent")
            skipped_actions = list_follow_up_actions(queue_path, run_date="2026-04-26", status="skipped")

        self.assertEqual([action["action_id"] for action in sent_actions], ["FU-2026-04-26-01-R1"])
        self.assertEqual([action["action_id"] for action in skipped_actions], ["FU-2026-04-26-O1"])

    def test_merge_does_not_apply_new_candidate_metadata_to_skipped_action(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "follow_up_action_queue.json"
            merge_follow_up_actions(
                [
                    {
                        "action_id": "FU-2026-04-26-01-R1",
                        "date": "2026-04-26",
                        "kind": "reply_comment",
                        "status": "drafted",
                        "platform": "bluesky",
                        "target_url": "https://bsky.app/profile/old.example/post/3old",
                        "target_author_handle": "wrong.example",
                        "target_author_display_name": "Wrong Candidate",
                        "target_reason": "Stale metadata.",
                        "draft_text": "Draft",
                        "approved_text": "",
                        "created_at": "2026-04-26T14:00:00+00:00",
                        "updated_at": "2026-04-26T14:00:00+00:00",
                        "notes": [],
                    }
                ],
                path=queue_path,
            )
            skip_follow_up_action("FU-2026-04-26-01-R1", note="Bad fit", path=queue_path)

            merge_follow_up_actions(
                [
                    {
                        "action_id": "FU-2026-04-26-01-R1",
                        "date": "2026-04-26",
                        "kind": "reply_comment",
                        "status": "drafted",
                        "platform": "bluesky",
                        "target_url": "https://bsky.app/profile/new.example/post/3new",
                        "target_author_display_name": "New Candidate",
                        "target_reason": "New discovery result.",
                        "draft_text": "Draft",
                        "approved_text": "",
                        "created_at": "2026-04-26T15:00:00+00:00",
                        "updated_at": "2026-04-26T15:00:00+00:00",
                        "notes": [],
                    }
                ],
                path=queue_path,
            )
            skipped = list_follow_up_actions(queue_path, status="skipped")[0]

        self.assertEqual(skipped["target_url"], "https://bsky.app/profile/old.example/post/3old")
        self.assertNotIn("target_author_display_name", skipped)
        self.assertNotIn("target_reason", skipped)

    def test_merge_refreshes_drafted_auto_candidate_target(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "follow_up_action_queue.json"
            merge_follow_up_actions(
                [
                    {
                        "action_id": "FU-2026-04-26-01-R1",
                        "date": "2026-04-26",
                        "kind": "reply_comment",
                        "status": "drafted",
                        "platform": "instagram",
                        "target_url": "https://www.instagram.com/explore/tags/old/",
                        "draft_text": "Draft",
                        "approved_text": "",
                        "created_at": "2026-04-26T14:00:00+00:00",
                        "updated_at": "2026-04-26T14:00:00+00:00",
                        "notes": [],
                    }
                ],
                path=queue_path,
            )

            merge_follow_up_actions(
                [
                    {
                        "action_id": "FU-2026-04-26-01-R1",
                        "date": "2026-04-26",
                        "kind": "reply_comment",
                        "status": "drafted",
                        "platform": "instagram",
                        "target_url": "https://www.instagram.com/explore/tags/new/",
                        "draft_text": "Draft",
                        "approved_text": "",
                        "created_at": "2026-04-26T15:00:00+00:00",
                        "updated_at": "2026-04-26T15:00:00+00:00",
                        "notes": [],
                    }
                ],
                path=queue_path,
            )
            drafted = list_follow_up_actions(queue_path, status="drafted")[0]

        self.assertEqual(drafted["target_url"], "https://www.instagram.com/explore/tags/new/")

    def test_load_posts_for_plan_finds_latest_matching_platform_file(self):
        plan = {
            "plan_date": "2026-04-26",
            "campaign": "coloradans_against",
            "planned_posts": [
                {
                    "slot": 1,
                    "platform": "bluesky",
                    "shirt_id": "shirt-1",
                    "title": "Coloradans Against Craft Beer",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            older = output_dir / "posts_2026-04-26_bluesky_20260426T120000Z_old.json"
            newer = output_dir / "posts_2026-04-26_bluesky_20260426T130000Z_new.json"
            older.write_text(json.dumps([{"shirt_id": "shirt-1", "title": "Old", "campaign": "coloradans_against"}]))
            newer.write_text(json.dumps([{"shirt_id": "shirt-1", "title": "New", "campaign": "coloradans_against"}]))

            refs = load_posts_for_plan(plan, output_dir=output_dir)

        self.assertEqual(refs[0]["post"]["title"], "New")
        self.assertTrue(refs[0]["source_file"].endswith("posts_2026-04-26_bluesky_20260426T130000Z_new.json"))

    def test_load_publish_records_filters_by_date_and_platform(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "data"
            log_dir.mkdir()
            (log_dir / "bluesky_publish_log.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"logged_at": "2026-04-25T12:00:00+00:00", "status": "published", "shirt_id": "old"}),
                        json.dumps({"logged_at": "2026-04-26T12:00:00+00:00", "status": "published", "shirt_id": "new"}),
                        json.dumps({"logged_at": "2026-04-26T13:00:00+00:00", "status": "draft", "shirt_id": "draft"}),
                    ]
                )
                + "\n"
            )

            records = load_publish_records("2026-04-26", log_dir=log_dir, platforms=["bluesky"])

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["shirt_id"], "new")
        self.assertEqual(records[0]["platform"], "bluesky")

    def test_write_follow_up_brief_writes_markdown_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            destination = write_follow_up_brief("hello\n", "2026-04-26", output_dir=Path(tmpdir))

            self.assertEqual(destination.name, "follow_up_2026-04-26.md")
            self.assertEqual(destination.read_text(), "hello\n")

    def test_load_follow_up_queue_recovers_from_malformed_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "queue.json"
            queue_path.write_text("")

            queue = load_follow_up_queue(queue_path)

        self.assertEqual(queue, {"actions": []})


if __name__ == "__main__":
    unittest.main()
