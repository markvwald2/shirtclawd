import importlib.util
import json
import pathlib
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from bot.post_generator import load_content_formats, load_theme_formats
from bot.selector import load_history


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "generate_posts.py"
SPEC = importlib.util.spec_from_file_location("generate_posts_module", MODULE_PATH)
GENERATE_POSTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATE_POSTS)


class GenerateFromPlanTests(unittest.TestCase):
    def test_generate_from_plan_writes_platform_files_and_history(self):
        inventory = [
            {
                "shirt_id": "1",
                "title": "Alpha",
                "url": "https://example.com/alpha",
                "image_url": "https://example.com/alpha.jpg",
                "theme": "sports",
                "tags": ["sports"],
                "status": "available",
                "is_promotable": True,
                "promotion_status": "promote",
            },
            {
                "shirt_id": "2",
                "title": "Beta",
                "url": "https://example.com/beta",
                "image_url": "https://example.com/beta.jpg",
                "theme": "movies",
                "tags": ["movies"],
                "status": "available",
                "is_promotable": True,
                "promotion_status": "promote",
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            plan_path = tmp_path / "daily_plan.json"
            history_path = tmp_path / "history.json"
            output_dir = tmp_path / "output"
            plan_path.write_text(
                json.dumps(
                    {
                        "plan_date": "2026-03-14",
                        "ai_model": "gpt-4o-mini",
                        "writer_mode": "ai",
                        "planned_posts": [
                            {"slot": 1, "platform": "x", "shirt_id": "1", "approval_required": True, "approval_status": "pending"},
                            {"slot": 2, "platform": "instagram", "shirt_id": "2", "approval_required": True, "approval_status": "pending"},
                        ],
                    }
                )
            )
            args = Namespace(
                plan=str(plan_path),
                history=str(history_path),
                output_dir=str(output_dir),
                seed=7,
                writer_mode="ai",
                ai_model="gpt-4o-mini",
                max_ai_calls=3,
                max_total_tokens=12000,
                max_estimated_cost=1.0,
            )

            with patch.object(
                GENERATE_POSTS,
                "generate_post_components",
                return_value={
                    "components": {
                        "headline": "AI headline",
                        "caption": "AI caption",
                        "hashtags": ["#test"],
                        "alt_text": "AI alt text",
                        "post_type": "ai_custom",
                    },
                    "usage": {},
                },
            ):
                GENERATE_POSTS.generate_from_plan(
                    args=args,
                    inventory=inventory,
                    theme_formats=load_theme_formats(),
                    content_formats=load_content_formats(),
                    pricing={},
                )

            x_posts = json.loads((output_dir / "posts_2026-03-14_x.json").read_text())
            instagram_posts = json.loads((output_dir / "posts_2026-03-14_instagram.json").read_text())

            self.assertEqual(len(x_posts), 1)
            self.assertEqual(len(instagram_posts), 1)
            self.assertEqual(x_posts[0]["plan_slot"], 1)
            self.assertEqual(x_posts[0]["approval_status"], "pending")
            self.assertEqual(instagram_posts[0]["plan_slot"], 2)
            self.assertEqual(instagram_posts[0]["planned_platform"], "instagram")

            history = load_history(history_path)
            self.assertEqual(len(history), 2)
            self.assertEqual({entry["shirt_id"] for entry in history}, {"1", "2"})

    def test_generate_from_plan_errors_when_planned_shirt_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            plan_path = tmp_path / "daily_plan.json"
            plan_path.write_text(
                json.dumps(
                    {
                        "plan_date": "2026-03-14",
                        "ai_model": "gpt-4o-mini",
                        "writer_mode": "ai",
                        "planned_posts": [
                            {"slot": 1, "platform": "x", "shirt_id": "missing", "approval_required": True, "approval_status": "pending"},
                        ],
                    }
                )
            )
            args = Namespace(
                plan=str(plan_path),
                history=str(tmp_path / "history.json"),
                output_dir=str(tmp_path / "output"),
                seed=7,
                writer_mode="ai",
                ai_model="gpt-4o-mini",
                max_ai_calls=3,
                max_total_tokens=12000,
                max_estimated_cost=1.0,
            )

            with self.assertRaises(SystemExit):
                GENERATE_POSTS.generate_from_plan(
                    args=args,
                    inventory=[],
                    theme_formats=load_theme_formats(),
                    content_formats=load_content_formats(),
                    pricing={},
                )


if __name__ == "__main__":
    unittest.main()
