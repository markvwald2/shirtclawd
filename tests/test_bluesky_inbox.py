import unittest

from bot.bluesky_inbox import fetch_bluesky_inbox_items, inbox_item_from_notification


class BlueskyInboxTests(unittest.TestCase):
    def test_inbox_item_from_notification_builds_actionable_reply(self):
        item = inbox_item_from_notification(
            {
                "uri": "at://did:plc:abc/app.bsky.feed.post/3reply",
                "cid": "cid-1",
                "reason": "reply",
                "reasonSubject": "at://did:plc:me/app.bsky.feed.post/3root",
                "indexedAt": "2026-04-26T14:00:00Z",
                "author": {
                    "handle": "denverpost.com",
                    "displayName": "The Denver Post",
                    "did": "did:plc:abc",
                },
                "record": {"text": "Craft beer is civic infrastructure."},
                "isRead": False,
            }
        )

        self.assertEqual(item["reason"], "reply")
        self.assertEqual(item["author_handle"], "denverpost.com")
        self.assertEqual(item["url"], "https://bsky.app/profile/denverpost.com/post/3reply")
        self.assertEqual(item["text"], "Craft beer is civic infrastructure.")

    def test_fetch_bluesky_inbox_items_filters_non_actionable_and_old_items(self):
        notifications = [
            {
                "uri": "at://did:plc:abc/app.bsky.feed.post/3old",
                "cid": "cid-old",
                "reason": "reply",
                "indexedAt": "2026-04-26T13:59:59Z",
                "author": {"handle": "old.example"},
                "record": {"text": "Old"},
            },
            {
                "uri": "at://did:plc:abc/app.bsky.feed.post/3like",
                "cid": "cid-like",
                "reason": "like",
                "indexedAt": "2026-04-26T14:30:00Z",
                "author": {"handle": "fan.example"},
                "record": {},
            },
            {
                "uri": "at://did:plc:abc/app.bsky.feed.post/3new",
                "cid": "cid-new",
                "reason": "mention",
                "indexedAt": "2026-04-26T14:30:00Z",
                "author": {"handle": "new.example"},
                "record": {"text": "Please advise."},
            },
        ]

        items = fetch_bluesky_inbox_items(
            since="2026-04-26T14:00:00Z",
            list_notifications_fn=lambda **_: notifications,
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["uri"], "at://did:plc:abc/app.bsky.feed.post/3new")


if __name__ == "__main__":
    unittest.main()
