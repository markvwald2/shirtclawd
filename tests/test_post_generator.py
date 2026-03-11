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

    def test_build_posts_supports_new_platform_rules(self):
        shirts = [
            {
                "shirt_id": "abc123",
                "title": "Addison CTA Blue Line",
                "url": "https://example.com/addison",
                "image_url": "https://example.com/addison.jpg",
                "theme": "transportation",
                "sub_theme": "CTA stops",
                "tags": ["transportation", "cta", "chicago", "trains", "city"],
            }
        ]

        posts = build_posts(
            shirts,
            load_theme_formats(),
            load_content_formats(),
            "bluesky",
            random_source(7),
        )

        self.assertEqual(posts[0]["platform"], "bluesky")
        self.assertLessEqual(len(posts[0]["hashtags"]), 2)
        self.assertIn("Tell us if the reference lands.", posts[0]["caption"])

        tiktok_posts = build_posts(
            shirts,
            load_theme_formats(),
            load_content_formats(),
            "tiktok",
            random_source(7),
        )

        self.assertEqual(tiktok_posts[0]["platform"], "tiktok")
        self.assertLessEqual(len(tiktok_posts[0]["hashtags"]), 4)
        self.assertIn("Drop this in the group chat.", tiktok_posts[0]["caption"])

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
        self.assertEqual(post["post_type"], "ai_custom")

    def test_build_ai_post_cleans_malformed_hashtags(self):
        shirt = {
            "shirt_id": "abc123",
            "title": "Bells Beach",
            "url": "https://example.com/bells",
            "image_url": "https://example.com/bells.jpg",
            "theme": "movies",
            "tags": ["movies"],
        }
        components = {
            "headline": "Ride the Wave of Nostalgia",
            "caption": "A custom caption",
            "hashtags": ["#PointBreak", "#@SurfCulture", "#\u200b#90sMovies"],
            "alt_text": "A product image for Bells Beach.",
            "post_type": "social_post",
        }

        post = build_ai_post(
            shirt,
            components,
            load_content_formats(),
            "x",
            random_source(7),
        )

        self.assertEqual(post["hashtags"], ["#PointBreak", "#SurfCulture"])
        self.assertEqual(post["post_type"], "ai_custom")


if __name__ == "__main__":
    unittest.main()
