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
