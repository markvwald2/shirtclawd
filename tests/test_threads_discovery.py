import json
import unittest
from datetime import datetime, timezone

from bot.threads_discovery import (
    candidate_from_media,
    find_reply_candidates,
    normalize_username,
    threads_access_hint,
    threads_search_url,
)


class ThreadsDiscoveryTests(unittest.TestCase):
    def test_find_reply_candidates_filters_replies_and_old_posts(self):
        now = datetime(2026, 4, 26, 14, 0, tzinfo=timezone.utc)

        def fake_search(query, limit, credentials=None):
            return [
                sample_media(
                    media_id="fresh",
                    username="denverrunner",
                    text="Denver craft beer after a long run is the whole plan.",
                    timestamp="2026-04-26T10:00:00Z",
                ),
                sample_media(
                    media_id="reply",
                    username="replyuser",
                    text="Reply text",
                    timestamp="2026-04-26T10:00:00Z",
                    is_reply=True,
                ),
                sample_media(
                    media_id="old",
                    username="olduser",
                    text="Denver craft beer",
                    timestamp="2026-03-01T10:00:00Z",
                ),
            ]

        candidates = find_reply_candidates(
            ["Denver craft beer"],
            now=now,
            search_media_fn=fake_search,
            max_age_days=21,
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["author_handle"], "denverrunner")
        self.assertEqual(candidates[0]["url"], "https://www.threads.net/@denverrunner/post/fresh")
        self.assertIn("Threads post", candidates[0]["reason"])

    def test_candidate_from_media_excludes_own_username(self):
        now = datetime(2026, 4, 26, 14, 0, tzinfo=timezone.utc)

        candidate = candidate_from_media(
            sample_media(username="3rdstringshirts"),
            query="Colorado hiking",
            now=now,
            exclude_usernames={"3rdstringshirts"},
        )

        self.assertIsNone(candidate)

    def test_normalize_username(self):
        self.assertEqual(normalize_username("@ThirdStringShirts "), "thirdstringshirts")

    def test_find_reply_candidates_falls_back_to_manual_search(self):
        def fake_search(query, limit, credentials=None):
            return []

        candidates = find_reply_candidates(["Colorado fourteeners"], search_media_fn=fake_search)

        self.assertEqual(candidates[0]["url"], "https://www.threads.net/search?q=Colorado+fourteeners")
        self.assertTrue(candidates[0]["manual_review"])

    def test_threads_search_url_encodes_query(self):
        self.assertEqual(threads_search_url("Colorado craft beer"), "https://www.threads.net/search?q=Colorado+craft+beer")

    def test_threads_access_hint_explains_access_tier_errors(self):
        hint = threads_access_hint(
            json.dumps(
                {
                    "error": {
                        "code": 10,
                        "error_subcode": 4279067,
                        "error_user_title": "App Does Not Have Sufficient Access Tier",
                        "error_user_msg": "App review might be required.",
                    }
                }
            )
        )

        self.assertIn("access tier", hint.lower())


def sample_media(
    media_id="abc123",
    username="example",
    text="Colorado craft beer",
    timestamp="2026-04-26T10:00:00Z",
    has_replies=False,
    is_reply=False,
    is_quote_post=False,
):
    return {
        "id": media_id,
        "username": username,
        "text": text,
        "timestamp": timestamp,
        "permalink": f"https://www.threads.net/@{username}/post/{media_id}",
        "has_replies": has_replies,
        "is_reply": is_reply,
        "is_quote_post": is_quote_post,
        "media_type": "TEXT",
    }


if __name__ == "__main__":
    unittest.main()
