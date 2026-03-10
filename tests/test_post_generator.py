import unittest

from bot.post_generator import (
    build_ai_post,
    build_posts,
    load_content_formats,
    load_theme_formats,
    random_source,
)


class PostGeneratorTests(unittest.TestCase):
    def test_build_posts_applies_platform_rules(self):
        shirts = [
            {
                "shirt_id": "abc123",
                "title": "Addison CTA Blue Line",
                "url": "https://example.com/addison",
                "image_url": "https://example.com/addison.jpg",
                "theme": "transportation",
                "sub_theme": "CTA stops",
                "tags": ["transportation", "cta", "chicago"],
            }
        ]

        posts = build_posts(
            shirts,
            load_theme_formats(),
            load_content_formats(),
            "x",
            random_source(7),
        )

        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["platform"], "x")
        self.assertLessEqual(len(posts[0]["hashtags"]), 2)
        self.assertIn("Reply if you get the reference.", posts[0]["caption"])
        self.assertIn("#thirdstringshirts", posts[0]["caption"])

    def test_build_ai_post_normalizes_ai_output(self):
        shirt = {
            "shirt_id": "abc123",
            "title": "Biblical Sense",
            "url": "https://example.com/biblical",
            "image_url": "https://example.com/biblical.jpg",
            "theme": "religion",
            "tags": ["religion"],
        }
        components = {
            "headline": "Biblical Sense goes sharper",
            "caption": "A custom caption with the URL https://example.com/biblical",
            "hashtags": ["thirdstringshirts", "#religion", "#religion"],
            "alt_text": "A product image for Biblical Sense.",
            "post_type": "ai_custom",
        }

        post = build_ai_post(
            shirt,
            components,
            load_content_formats(),
            "facebook",
            random_source(7),
        )

        self.assertEqual(post["writer_mode"], "ai")
        self.assertEqual(post["headline"], "Featured: Biblical Sense goes sharper")
        self.assertEqual(post["hashtags"], ["#thirdstringshirts", "#religion"])


if __name__ == "__main__":
    unittest.main()
