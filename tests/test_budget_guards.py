import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "generate_posts.py"
SPEC = importlib.util.spec_from_file_location("generate_posts_module", MODULE_PATH)
GENERATE_POSTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATE_POSTS)

from bot.post_generator import load_content_formats, load_theme_formats, random_source
from bot.usage_logger import create_run_context


class BudgetGuardTests(unittest.TestCase):
    def test_budget_guard_stops_generation_before_ai_attempt(self):
        shirts = [
            {
                "shirt_id": "abc123",
                "title": "Biblical Sense",
                "url": "https://example.com/biblical",
                "image_url": "https://example.com/biblical.jpg",
                "theme": "religion",
                "tags": ["religion"],
                "status": "available",
            }
        ]
        run_context = create_run_context(
            "x",
            "ai",
            "gpt-4o-mini",
            1,
            max_ai_calls=0,
        )

        with self.assertRaises(SystemExit):
            GENERATE_POSTS.build_posts_for_mode(
                shirts=shirts,
                theme_formats=load_theme_formats(),
                content_formats=load_content_formats(),
                platform="x",
                rng=random_source(7),
                writer_mode="ai",
                ai_model="gpt-4o-mini",
                run_context=run_context,
                pricing={},
            )


if __name__ == "__main__":
    unittest.main()
