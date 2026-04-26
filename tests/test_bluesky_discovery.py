import unittest
from datetime import datetime, timezone

from bot.bluesky_discovery import (
    bsky_post_url,
    candidate_from_post,
    find_reply_candidates,
    rkey_from_at_uri,
)


class BlueskyDiscoveryTests(unittest.TestCase):
    def test_find_reply_candidates_prefers_fresh_relevant_posts(self):
        now = datetime(2026, 4, 26, 14, 0, tzinfo=timezone.utc)
        posts_by_query = {
            "Colorado craft beer": [
                sample_post(
                    rkey="3fresh",
                    handle="denverpost.com",
                    text="Colorado breweries won 26 medals at the World Beer Cup.",
                    created_at="2026-04-25T10:44:11.584Z",
                    likes=3,
                    reposts=1,
                ),
                sample_post(
                    rkey="3old",
                    handle="oldnews.example",
                    text="Colorado craft beer news from last season.",
                    created_at="2026-03-01T10:44:11.584Z",
                    likes=100,
                ),
            ],
            "Denver craft beer": [
                sample_post(
                    rkey="3reply",
                    handle="reply.example",
                    text="Denver craft beer reply",
                    created_at="2026-04-26T10:44:11.584Z",
                    reply=True,
                )
            ],
        }

        def fake_search(query, limit):
            return posts_by_query[query]

        candidates = find_reply_candidates(
            ["Colorado craft beer", "Denver craft beer"],
            now=now,
            search_posts_fn=fake_search,
            max_age_days=21,
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["author_handle"], "denverpost.com")
        self.assertEqual(candidates[0]["url"], "https://bsky.app/profile/denverpost.com/post/3fresh")
        self.assertIn("World Beer Cup", candidates[0]["text"])
        self.assertIn("matching `Colorado craft beer`", candidates[0]["reason"])

    def test_candidate_from_post_excludes_own_handle(self):
        now = datetime(2026, 4, 26, 14, 0, tzinfo=timezone.utc)

        candidate = candidate_from_post(
            sample_post(handle="3rdstringshirts.bsky.social"),
            query="Colorado craft beer",
            now=now,
            exclude_handles={"3rdstringshirts.bsky.social"},
        )

        self.assertIsNone(candidate)

    def test_bsky_post_url_uses_handle_and_rkey(self):
        uri = "at://did:plc:abc/app.bsky.feed.post/3kabc"

        self.assertEqual(rkey_from_at_uri(uri), "3kabc")
        self.assertEqual(bsky_post_url("example.com", uri), "https://bsky.app/profile/example.com/post/3kabc")


def sample_post(
    rkey="3kabc",
    handle="example.com",
    text="Colorado craft beer",
    created_at="2026-04-26T10:00:00Z",
    likes=0,
    reposts=0,
    replies=0,
    quotes=0,
    reply=False,
):
    record = {
        "text": text,
        "createdAt": created_at,
    }
    if reply:
        record["reply"] = {
            "root": {"uri": "at://did:plc:root/app.bsky.feed.post/root", "cid": "root-cid"},
            "parent": {"uri": "at://did:plc:parent/app.bsky.feed.post/parent", "cid": "parent-cid"},
        }
    return {
        "uri": f"at://did:plc:abc/app.bsky.feed.post/{rkey}",
        "cid": f"{rkey}-cid",
        "author": {
            "did": "did:plc:abc",
            "handle": handle,
            "displayName": handle,
        },
        "record": record,
        "likeCount": likes,
        "repostCount": reposts,
        "replyCount": replies,
        "quoteCount": quotes,
    }


if __name__ == "__main__":
    unittest.main()
