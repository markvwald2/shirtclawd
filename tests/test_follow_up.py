import json
import tempfile
import unittest
from pathlib import Path

from bot.follow_up import (
    approve_follow_up_action,
    build_follow_up_actions,
    build_follow_up_brief,
    cleanup_follow_up_backlog,
    daily_plan_date_for_path,
    find_latest_daily_plan,
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
                    "active_offer": "20% off all Spreadshirt orders",
                    "offer_starts_on": "2026-05-15",
                    "offer_ends_on": "2026-05-19",
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

    def test_build_follow_up_actions_automation_only_keeps_executable_targets(self):
        plan = {
            "plan_date": "2026-04-26",
            "campaign": "coloradans_against",
            "planned_posts": [
                {
                    "slot": 1,
                    "platform": "threads",
                    "shirt_id": "shirt-1",
                    "title": "Coloradans Against Fourteeners",
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

        actions = build_follow_up_actions(
            plan,
            post_refs,
            [],
            run_date="2026-04-26",
            generated_at="2026-04-26T14:00:00+00:00",
            target_discovery={
                "FU-2026-04-26-01": {
                    "candidates": [
                        {
                            "platform": "threads",
                            "url": "https://www.threads.net/@local/post/abc",
                            "uri": "thread123",
                            "author_display_name": "@local",
                            "query": "Colorado fourteeners",
                            "reason": "Fresh Threads post.",
                            "created_at": "2026-04-25T10:44:11+00:00",
                            "score": 72.5,
                        }
                    ]
                }
            },
            automation_only=True,
        )

        self.assertEqual([action["action_id"] for action in actions], ["FU-2026-04-26-01-R1"])
        self.assertEqual(actions[0]["target_thread_id"], "thread123")

    def test_build_follow_up_actions_automation_only_drops_manual_candidates(self):
        plan = {
            "plan_date": "2026-04-26",
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
        post_refs = [{"entry": plan["planned_posts"][0], "post": plan["planned_posts"][0]}]

        actions = build_follow_up_actions(
            plan,
            post_refs,
            [],
            run_date="2026-04-26",
            target_discovery={
                "FU-2026-04-26-01": {
                    "candidates": [
                        {
                            "platform": "facebook",
                            "url": "https://www.facebook.com/search/posts/?q=triathlons",
                            "uri": "https://www.facebook.com/search/posts/?q=triathlons",
                            "manual_review": True,
                        }
                    ]
                }
            },
            automation_only=True,
        )

        self.assertEqual(actions, [])

    def test_build_follow_up_actions_automation_only_drops_instagram_media_without_comment_id(self):
        plan = {
            "plan_date": "2026-04-26",
            "campaign": "coloradans_against",
            "planned_posts": [
                {
                    "slot": 1,
                    "platform": "instagram",
                    "shirt_id": "shirt-1",
                    "title": "Coloradans Against Hiking",
                    "series": "Coloradans Against",
                    "content_goal": "conversation",
                    "cta_goal": "reply",
                }
            ],
        }
        post_refs = [{"entry": plan["planned_posts"][0], "post": plan["planned_posts"][0]}]

        actions = build_follow_up_actions(
            plan,
            post_refs,
            [],
            run_date="2026-04-26",
            target_discovery={
                "FU-2026-04-26-01": {
                    "candidates": [
                        {
                            "platform": "instagram",
                            "url": "https://www.instagram.com/p/example/",
                            "uri": "media123",
                            "author_display_name": "Instagram #hiking",
                        }
                    ]
                }
            },
            automation_only=True,
        )

        self.assertEqual(actions, [])

    def test_build_follow_up_actions_automation_only_keeps_instagram_comment_id(self):
        plan = {
            "plan_date": "2026-04-26",
            "campaign": "coloradans_against",
            "planned_posts": [
                {
                    "slot": 1,
                    "platform": "instagram",
                    "shirt_id": "shirt-1",
                    "title": "Coloradans Against Hiking",
                    "series": "Coloradans Against",
                    "content_goal": "conversation",
                    "cta_goal": "reply",
                }
            ],
        }
        post_refs = [{"entry": plan["planned_posts"][0], "post": plan["planned_posts"][0]}]

        actions = build_follow_up_actions(
            plan,
            post_refs,
            [],
            run_date="2026-04-26",
            target_discovery={
                "FU-2026-04-26-01": {
                    "candidates": [
                        {
                            "platform": "instagram",
                            "url": "https://www.instagram.com/p/example/",
                            "uri": "media123",
                            "comment_id": "comment123",
                            "author_display_name": "Owned media comment",
                        }
                    ]
                }
            },
            automation_only=True,
        )

        self.assertEqual([action["action_id"] for action in actions], ["FU-2026-04-26-01-R1"])
        self.assertEqual(actions[0]["target_comment_id"], "comment123")

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

    def test_merge_replace_run_date_drops_stale_current_date_actions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "follow_up_action_queue.json"
            merge_follow_up_actions(
                [
                    {
                        "action_id": "FU-2026-04-26-O1",
                        "date": "2026-04-26",
                        "kind": "outreach_dm",
                        "status": "drafted",
                        "draft_text": "Manual",
                        "approved_text": "",
                        "created_at": "2026-04-26T14:00:00+00:00",
                        "updated_at": "2026-04-26T14:00:00+00:00",
                        "notes": [],
                    }
                ],
                path=queue_path,
            )

            merge_follow_up_actions([], path=queue_path, replace_run_date="2026-04-26")

            self.assertEqual(list_follow_up_actions(queue_path, run_date="2026-04-26"), [])

    def test_cleanup_follow_up_backlog_skips_duplicate_and_stale_manual_actions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "follow_up_action_queue.json"
            queue_path.write_text(
                json.dumps(
                    {
                        "actions": [
                            {
                                "action_id": "FU-2026-04-26-02-R1",
                                "date": "2026-04-26",
                                "kind": "reply_comment",
                                "status": "approved",
                                "platform": "instagram",
                                "target_url": "https://www.instagram.com/explore/tags/coloradohiking/",
                                "draft_text": "Old",
                                "approved_text": "Old",
                                "created_at": "2026-04-26T14:00:00+00:00",
                                "updated_at": "2026-04-26T14:00:00+00:00",
                                "notes": [],
                            },
                            {
                                "action_id": "FU-2026-04-27-O1",
                                "date": "2026-04-27",
                                "kind": "outreach_dm",
                                "status": "approved",
                                "platform": "manual",
                                "target_type": "One-off local newsletter",
                                "draft_text": "Stale",
                                "approved_text": "Stale",
                                "created_at": "2026-04-27T14:00:00+00:00",
                                "updated_at": "2026-04-27T14:00:00+00:00",
                                "notes": [],
                            },
                            {
                                "action_id": "FU-2026-04-29-02-R1",
                                "date": "2026-04-29",
                                "kind": "reply_comment",
                                "status": "drafted",
                                "platform": "instagram",
                                "target_url": "https://www.instagram.com/explore/tags/coloradohiking/",
                                "draft_text": "Newest",
                                "approved_text": "",
                                "created_at": "2026-04-29T14:00:00+00:00",
                                "updated_at": "2026-04-29T14:00:00+00:00",
                                "notes": [],
                            },
                            {
                                "action_id": "FU-2026-04-26-01-R1",
                                "date": "2026-04-26",
                                "kind": "reply_comment",
                                "status": "approved",
                                "platform": "bluesky",
                                "target_url": "https://bsky.app/profile/example/post/3abc",
                                "draft_text": "API-safe",
                                "approved_text": "API-safe",
                                "created_at": "2026-04-26T14:00:00+00:00",
                                "updated_at": "2026-04-26T14:00:00+00:00",
                                "notes": [],
                            },
                        ]
                    }
                )
            )

            summary = cleanup_follow_up_backlog(
                path=queue_path,
                reference_date="2026-04-29",
                max_carryover_days=1,
            )
            actions = {action["action_id"]: action for action in list_follow_up_actions(queue_path)}

        self.assertEqual(summary["skipped_duplicate_count"], 1)
        self.assertEqual(summary["skipped_stale_count"], 1)
        self.assertEqual(actions["FU-2026-04-26-02-R1"]["status"], "skipped")
        self.assertEqual(actions["FU-2026-04-27-O1"]["status"], "skipped")
        self.assertEqual(actions["FU-2026-04-29-02-R1"]["status"], "drafted")
        self.assertEqual(actions["FU-2026-04-26-01-R1"]["status"], "approved")

    def test_find_latest_daily_plan_can_use_latest_prior_plan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            for plan_date in ("2026-04-26", "2026-04-29", "2026-05-03"):
                (output_dir / f"daily_plan_{plan_date}.json").write_text(
                    json.dumps({"plan_date": plan_date, "planned_posts": []})
                )
            manual_path = output_dir / "daily_plan_2026-04-30_manual_now.json"
            manual_path.write_text(json.dumps({"planned_posts": []}))

            latest_prior = find_latest_daily_plan(output_dir, before_date="2026-05-03")
            latest_any = find_latest_daily_plan(output_dir)

        self.assertEqual(latest_prior.name, "daily_plan_2026-04-30_manual_now.json")
        self.assertEqual(daily_plan_date_for_path(latest_prior), "2026-04-30")
        self.assertEqual(latest_any.name, "daily_plan_2026-05-03.json")

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

    def test_merge_preserves_approved_threads_target_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "follow_up_action_queue.json"
            merge_follow_up_actions(
                [
                    {
                        "action_id": "FU-2026-04-26-04-R1",
                        "date": "2026-04-26",
                        "kind": "reply_comment",
                        "status": "drafted",
                        "platform": "threads",
                        "target_url": "https://www.threads.net/@local/post/abc",
                        "target_thread_id": "thread123",
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

            merge_follow_up_actions(
                [
                    {
                        "action_id": "FU-2026-04-26-04-R1",
                        "date": "2026-04-26",
                        "kind": "reply_comment",
                        "status": "drafted",
                        "platform": "threads",
                        "target_url": "https://www.threads.net/search?q=fourteeners",
                        "draft_text": "Draft",
                        "approved_text": "",
                        "created_at": "2026-04-26T15:00:00+00:00",
                        "updated_at": "2026-04-26T15:00:00+00:00",
                        "notes": [],
                    }
                ],
                path=queue_path,
            )
            approved = list_follow_up_actions(queue_path, status="approved")[0]

        self.assertEqual(approved["target_thread_id"], "thread123")

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
                        json.dumps({"logged_at": "2026-04-26T12:30:00+00:00", "status": "published_carousel", "shirt_id": "set"}),
                        json.dumps({"logged_at": "2026-04-26T13:00:00+00:00", "status": "draft", "shirt_id": "draft"}),
                    ]
                )
                + "\n"
            )

            records = load_publish_records("2026-04-26", log_dir=log_dir, platforms=["bluesky"])

        self.assertEqual([record["shirt_id"] for record in records], ["new", "set"])
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
