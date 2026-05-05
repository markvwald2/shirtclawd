import json
import unittest

from bot.ai_writer import build_user_prompt, parse_response


class AIWriterTests(unittest.TestCase):
    def test_build_user_prompt_includes_annotation_context(self):
        prompt = json.loads(
            build_user_prompt(
                {
                    "shirt_id": "abc123",
                    "title": "Biblical Sense",
                    "theme": "religion",
                    "tags": ["religion"],
                    "url": "https://example.com",
                    "image_url": "https://example.com/image.jpg",
                    "reference_summary": "A Bible-wordplay joke.",
                    "target_audience": ["church humor"],
                    "tone": "edgy_snarky",
                    "tone_notes": "Dry, sharp, and a little smug.",
                    "notes": "Use carefully on broad channels.",
                },
                "x",
            )
        )

        self.assertEqual(
            prompt["tone_preset"]["guidance"],
            "Dry, sharp, irreverent, and a little smug. Write for people who enjoy niche references and jokes with some bite. Keep it clever, not cheerful. Slight snark is good; forced edginess, generic hype, and overexplaining are not.",
        )
        self.assertTrue(prompt["tone_examples"])
        self.assertEqual(prompt["shirt"]["tone"], "edgy_snarky")
        self.assertEqual(prompt["shirt"]["tone_notes"], "Dry, sharp, and a little smug.")
        self.assertEqual(prompt["shirt"]["reference_summary"], "A Bible-wordplay joke.")
        self.assertEqual(prompt["shirt"]["target_audience"], ["church humor"])
        self.assertEqual(prompt["shirt"]["notes"], "Use carefully on broad channels.")

    def test_build_user_prompt_includes_campaign_content_context(self):
        prompt = json.loads(
            build_user_prompt(
                {
                    "shirt_id": "etsy_2649334247",
                    "title": "Coloradans Against Craft Beer",
                    "theme": "Coloradans Against",
                    "tags": ["colorado", "beer"],
                    "url": "https://example.com",
                    "image_url": "https://example.com/image.jpg",
                    "reference_summary": "A Colorado anti-cliche joke.",
                    "target_audience": ["Colorado locals"],
                },
                "instagram",
                post_context={
                    "campaign": "coloradans_against",
                    "series": "Coloradans Against",
                    "audience_lane": "colorado_regional_sarcasm",
                    "content_goal": "conversation",
                    "content_format": "group_chat_argument",
                    "cta_goal": "reply",
                    "campaign_prompt_guidance": "Invite a specific reply.",
                    "active_offer": "20% off all Spreadshirt orders",
                    "offer_starts_on": "2026-05-15",
                    "offer_ends_on": "2026-05-19",
                },
            )
        )

        self.assertEqual(prompt["post_context"]["campaign"], "coloradans_against")
        self.assertEqual(prompt["post_context"]["content_goal"], "conversation")
        self.assertIn("top-of-funnel conversation content", " ".join(prompt["requirements"]))
        self.assertIn("specific reply prompt", " ".join(prompt["requirements"]))
        self.assertIn("20% off all Spreadshirt orders from 2026-05-15 through 2026-05-19", " ".join(prompt["requirements"]))
        self.assertIn("do not force it", " ".join(prompt["requirements"]))

    def test_build_user_prompt_asks_direct_offer_to_mention_active_offer(self):
        prompt = json.loads(
            build_user_prompt(
                {
                    "shirt_id": "etsy_2613432644",
                    "title": "Coloradans Against Fourteeners",
                    "theme": "Coloradans Against",
                    "tags": ["colorado", "fourteeners"],
                    "url": "https://example.com",
                    "image_url": "https://example.com/image.jpg",
                },
                "threads",
                post_context={
                    "campaign": "coloradans_against",
                    "content_goal": "direct_offer",
                    "cta_goal": "buy",
                    "active_offer": "20% off all Spreadshirt orders",
                    "offer_starts_on": "2026-05-15",
                    "offer_ends_on": "2026-05-19",
                },
            )
        )

        requirements = " ".join(prompt["requirements"])
        self.assertIn("20% off all Spreadshirt orders from 2026-05-15 through 2026-05-19", requirements)
        self.assertIn("Mention it clearly", requirements)
        self.assertIn("Do not imply the sale is live outside that window", requirements)

    def test_build_user_prompt_guides_series_set_posts(self):
        prompt = json.loads(
            build_user_prompt(
                {
                    "shirt_id": "coloradans_against_set",
                    "title": "Coloradans Against Shirt Line",
                    "theme": "Coloradans Against",
                    "tags": ["colorado"],
                    "url": "https://example.com",
                    "image_url": "https://example.com/image.jpg",
                },
                "instagram",
                post_context={
                    "campaign": "coloradans_against",
                    "content_goal": "product_connected",
                    "content_format": "series_set",
                    "cta_goal": "buy",
                    "collection_title": "Coloradans Against Shirt Line",
                    "collection_size": 4,
                    "collection_items": [
                        {"shirt_id": "1", "title": "Coloradans Against Craft Beer"},
                        {"shirt_id": "2", "title": "Coloradans Against Hiking"},
                    ],
                },
            )
        )

        requirements = " ".join(prompt["requirements"])
        self.assertIn("multi-image set/carousel post", requirements)
        self.assertIn("whole line of shirts", requirements)
        self.assertEqual(prompt["post_context"]["collection_size"], "4")
        self.assertEqual(len(prompt["post_context"]["collection_items"]), 2)

    def test_parse_response_uses_output_text_json(self):
        raw_response = json.dumps(
            {
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 40,
                    "total_tokens": 140
                },
                "output_text": json.dumps(
                    {
                        "headline": "Biblical Sense lands",
                        "caption": "Custom copy with URL",
                        "hashtags": ["#thirdstringshirts"],
                        "alt_text": "Product shot.",
                        "post_type": "ai_custom",
                    }
                )
            }
        )

        parsed = parse_response(raw_response)

        self.assertEqual(parsed["components"]["post_type"], "ai_custom")
        self.assertEqual(parsed["components"]["hashtags"], ["#thirdstringshirts"])
        self.assertEqual(parsed["usage"]["total_tokens"], 140)


if __name__ == "__main__":
    unittest.main()
