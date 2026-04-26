import unittest
from datetime import datetime, timezone

from bot.instagram_discovery import build_hashtags, candidate_from_media, find_reply_candidates, instagram_hashtag_url


class InstagramDiscoveryTests(unittest.TestCase):
    def test_build_hashtags_uses_post_tags_topic_and_queries(self):
        tags = build_hashtags(
            "craft beer",
            post={"hashtags": ["#ColoradoBeer", "#ThirdStringShirts"]},
            queries=["Denver craft beer", "Colorado craft beer overrated"],
            max_hashtags=5,
        )

        self.assertEqual(tags[:3], ["coloradocraftbeer", "denvercraftbeer", "craftbeer"])
        self.assertIn("denvercraftbeer", tags)

    def test_find_reply_candidates_uses_recent_media(self):
        now = datetime(2026, 4, 26, 14, 0, tzinfo=timezone.utc)

        def fake_resolver(hashtag, credentials=None):
            return f"{hashtag}-id"

        def fake_search(hashtag_id, hashtag="", limit=25, credentials=None):
            return [
                sample_media(
                    media_id="fresh",
                    caption="Colorado hiking is just errands with altitude.",
                    timestamp="2026-04-26T10:00:00Z",
                    likes=12,
                    comments=2,
                ),
                sample_media(
                    media_id="old",
                    caption="Colorado hiking",
                    timestamp="2026-03-01T10:00:00Z",
                ),
            ]

        candidates = find_reply_candidates(
            ["coloradohiking"],
            now=now,
            resolve_hashtag_id_fn=fake_resolver,
            search_recent_media_fn=fake_search,
            max_age_days=7,
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["url"], "https://www.instagram.com/p/fresh/")
        self.assertEqual(candidates[0]["like_count"], 12)
        self.assertIn("Instagram media", candidates[0]["reason"])

    def test_candidate_from_media_requires_permalink(self):
        now = datetime(2026, 4, 26, 14, 0, tzinfo=timezone.utc)
        media = sample_media()
        media["permalink"] = ""

        self.assertIsNone(candidate_from_media(media, hashtag="colorado", now=now))

    def test_find_reply_candidates_falls_back_to_manual_hashtag_pages(self):
        def fake_resolver(hashtag, credentials=None):
            return f"{hashtag}-id"

        def fake_search(hashtag_id, hashtag="", limit=25, credentials=None):
            return []

        candidates = find_reply_candidates(
            ["coloradohiking"],
            resolve_hashtag_id_fn=fake_resolver,
            search_recent_media_fn=fake_search,
        )

        self.assertEqual(candidates[0]["url"], "https://www.instagram.com/explore/tags/coloradohiking/")
        self.assertTrue(candidates[0]["manual_review"])

    def test_instagram_hashtag_url(self):
        self.assertEqual(instagram_hashtag_url("coloradohiking"), "https://www.instagram.com/explore/tags/coloradohiking/")


def sample_media(
    media_id="abc123",
    caption="Colorado craft beer",
    timestamp="2026-04-26T10:00:00Z",
    likes=0,
    comments=0,
):
    return {
        "id": media_id,
        "caption": caption,
        "timestamp": timestamp,
        "permalink": f"https://www.instagram.com/p/{media_id}/",
        "like_count": likes,
        "comments_count": comments,
        "media_type": "IMAGE",
    }


if __name__ == "__main__":
    unittest.main()
