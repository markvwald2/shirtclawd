import unittest

from bot.post_generator import (
    build_ai_post,
    load_content_formats,
    random_source,
)


class PostGeneratorTests(unittest.TestCase):
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

    def test_build_ai_post_removes_raw_urls_from_instagram_caption(self):
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
            "hashtags": ["#religion"],
            "alt_text": "A product image for Biblical Sense.",
            "post_type": "ai_custom",
        }

        post = build_ai_post(
            shirt,
            components,
            load_content_formats(),
            "instagram",
            random_source(7),
        )

        self.assertNotIn("https://example.com", post["caption"])
        self.assertIn("\n\nLink in bio.\n\n#religion", post["caption"])

    def test_build_ai_post_does_not_duplicate_link_in_bio_cta(self):
        shirt = {
            "shirt_id": "abc123",
            "title": "Smell You Later",
            "url": "https://example.com/smell",
            "image_url": "https://example.com/smell.jpg",
            "theme": "funny",
            "tags": ["funny"],
        }
        components = {
            "headline": "A sharp goodbye",
            "caption": "Dive into the fine art of farewell at the link in bio.",
            "hashtags": ["#funny"],
            "alt_text": "A product image for Smell You Later.",
            "post_type": "ai_custom",
        }

        post = build_ai_post(
            shirt,
            components,
            load_content_formats(),
            "instagram",
            random_source(7),
        )

        self.assertEqual(post["caption"].lower().count("link in bio"), 1)

    def test_build_ai_post_moves_inline_hashtags_into_single_deduped_block(self):
        shirt = {
            "shirt_id": "abc123",
            "title": "Breaking Wind",
            "url": "https://example.com/breaking-wind",
            "image_url": "https://example.com/breaking-wind.jpg",
            "theme": "tv",
            "tags": ["tv"],
        }
        components = {
            "headline": "Chemistry with consequences",
            "caption": (
                "Because who needs chemistry when you've got gas? "
                "#BreakingBad #FartJokes #TVParody"
            ),
            "hashtags": ["#BreakingBad", "#FartJokes", "#TVParody"],
            "alt_text": "A product image for Breaking Wind.",
            "post_type": "ai_custom",
        }

        post = build_ai_post(
            shirt,
            components,
            load_content_formats(),
            "instagram",
            random_source(7),
        )

        self.assertEqual(post["caption"].count("#BreakingBad"), 1)
        self.assertEqual(post["caption"].count("#FartJokes"), 1)
        self.assertEqual(post["caption"].count("#TVParody"), 1)
        self.assertIn("\n\nLink in bio.\n\n#BreakingBad", post["caption"])
        self.assertTrue(post["caption"].endswith("#BreakingBad #FartJokes #TVParody"))
        self.assertNotIn("#BreakingBad #FartJokes #TVParody\n\n#BreakingBad", post["caption"])


if __name__ == "__main__":
    unittest.main()
