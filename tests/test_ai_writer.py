import json
import unittest

from bot.ai_writer import parse_response


class AIWriterTests(unittest.TestCase):
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
