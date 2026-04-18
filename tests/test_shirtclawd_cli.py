import importlib.util
import io
import pathlib
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "shirtclawd.py"
SPEC = importlib.util.spec_from_file_location("shirtclawd_module", MODULE_PATH)
SHIRTCLAWD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SHIRTCLAWD)


class ShirtclawdCliTests(unittest.TestCase):
    def test_run_ask_selects_matching_inventory_and_generates_posts(self):
        inventory = [
            {
                "shirt_id": "1",
                "title": "Coloradans Against Craft Beer",
                "url": "https://example.com/craft-beer",
                "image_url": "https://example.com/craft-beer.jpg",
                "theme": "Coloradans Against",
                "tags": ["colorado", "beer"],
                "status": "available",
                "is_promotable": True,
                "promotion_status": "promote",
            },
            {
                "shirt_id": "2",
                "title": "Coloradans Against Hiking",
                "url": "https://example.com/hiking",
                "image_url": "https://example.com/hiking.jpg",
                "theme": "Coloradans Against",
                "tags": ["colorado", "hiking"],
                "status": "available",
                "is_promotable": True,
                "promotion_status": "promote",
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            args = Namespace(
                prompt="Write 2 posts for Instagram for the Coloradans Against shirts",
                inventory=str(Path(tmpdir) / "inventory.json"),
                history=str(Path(tmpdir) / "history.json"),
                output_dir=str(Path(tmpdir) / "output"),
                seed=7,
                ai_model="gpt-4o-mini",
                max_ai_calls=3,
                max_total_tokens=12000,
                max_estimated_cost=0.02,
                publish=False,
            )

            with patch.object(SHIRTCLAWD, "load_inventory", return_value=inventory), patch.object(
                SHIRTCLAWD, "load_history", return_value=[]
            ), patch.object(
                SHIRTCLAWD,
                "generate_for_platform",
                return_value={
                    "posts": [{"shirt_id": "1"}, {"shirt_id": "2"}],
                    "destination": Path(tmpdir) / "output" / "posts_2026-04-04_instagram.json",
                    "history_entries": [{"shirt_id": "1"}, {"shirt_id": "2"}],
                    "summary_path": Path(tmpdir) / "output" / "run_summary.json",
                },
            ) as generate_mock, patch.object(
                SHIRTCLAWD, "append_generated_history"
            ) as append_mock:
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    SHIRTCLAWD.run_ask(args)

            selected_shirts = generate_mock.call_args.kwargs["shirts"]
            self.assertEqual([shirt["shirt_id"] for shirt in selected_shirts], ["1", "2"])
            self.assertEqual(generate_mock.call_args.kwargs["platform"], "instagram")
            append_mock.assert_called_once()
            rendered = stdout.getvalue()
            self.assertIn("Ready: 2 instagram posts.", rendered)
            self.assertIn("Matched: coloradans against shirts.", rendered)
            self.assertIn("- Coloradans Against Craft Beer", rendered)
            self.assertIn("posts_2026-04-04_instagram.json", rendered)
            self.assertIn("run_summary.json", rendered)

    def test_run_ask_can_publish_generated_instagram_posts(self):
        inventory = [
            {
                "shirt_id": "1",
                "title": "Caffeinate Hydrate Inebriate Replicate",
                "url": "https://example.com/caffeinate",
                "image_url": "https://example.com/caffeinate.png",
                "theme": "funny",
                "tags": ["coffee", "alcohol"],
                "status": "available",
                "is_promotable": True,
                "promotion_status": "promote",
            }
        ]

        generated = {
            "posts": [
                {
                    "shirt_id": "1",
                    "title": "Caffeinate Hydrate Inebriate Replicate",
                    "caption": "sample",
                    "image_url": "https://example.com/caffeinate.png",
                    "url": "https://example.com/caffeinate",
                }
            ],
            "destination": Path("/tmp") / "posts_2026-04-04_instagram.json",
            "history_entries": [{"shirt_id": "1"}],
            "summary_path": Path("/tmp") / "run_summary.json",
        }

        args = Namespace(
            prompt="Write 1 post for Instagram for the Caffeinate Hydrate Inebriate Replicate shirt",
            inventory="ignored.json",
            history="history.json",
            output_dir="output",
            seed=7,
            ai_model="gpt-4o-mini",
            max_ai_calls=3,
            max_total_tokens=12000,
            max_estimated_cost=0.02,
            publish=True,
        )

        with patch.object(SHIRTCLAWD, "load_inventory", return_value=inventory), patch.object(
            SHIRTCLAWD, "load_history", return_value=[]
        ), patch.object(
            SHIRTCLAWD, "generate_for_platform", return_value=generated
        ), patch.object(
            SHIRTCLAWD, "append_generated_history"
        ) as append_mock, patch.object(
            SHIRTCLAWD,
            "publish_instagram_post",
            return_value={"title": "Caffeinate Hydrate Inebriate Replicate", "instagram_media_id": "ig123"},
        ) as publish_mock:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                SHIRTCLAWD.run_ask(args)

        append_mock.assert_called_once()
        publish_mock.assert_called_once_with(generated["posts"][0], dry_run=False)
        rendered = stdout.getvalue()
        self.assertIn("Published:", rendered)
        self.assertIn("ig123", rendered)

    def test_run_ask_can_publish_generated_threads_posts(self):
        inventory = [
            {
                "shirt_id": "1",
                "title": "Caffeinate Hydrate Inebriate Replicate",
                "url": "https://example.com/caffeinate",
                "image_url": "https://example.com/caffeinate.png",
                "theme": "funny",
                "tags": ["coffee", "alcohol"],
                "status": "available",
                "is_promotable": True,
                "promotion_status": "promote",
            }
        ]

        generated = {
            "posts": [
                {
                    "shirt_id": "1",
                    "title": "Caffeinate Hydrate Inebriate Replicate",
                    "caption": "sample",
                    "image_url": "https://example.com/caffeinate.png",
                    "url": "https://example.com/caffeinate",
                }
            ],
            "destination": Path("/tmp") / "posts_2026-04-04_threads.json",
            "history_entries": [{"shirt_id": "1"}],
            "summary_path": Path("/tmp") / "run_summary.json",
        }

        args = Namespace(
            prompt="Write 1 post for Threads for the Caffeinate Hydrate Inebriate Replicate shirt",
            inventory="ignored.json",
            history="history.json",
            output_dir="output",
            seed=7,
            ai_model="gpt-4o-mini",
            max_ai_calls=3,
            max_total_tokens=12000,
            max_estimated_cost=0.02,
            publish=True,
        )

        with patch.object(SHIRTCLAWD, "load_inventory", return_value=inventory), patch.object(
            SHIRTCLAWD, "load_history", return_value=[]
        ), patch.object(
            SHIRTCLAWD, "generate_for_platform", return_value=generated
        ), patch.object(
            SHIRTCLAWD, "append_generated_history"
        ) as append_mock, patch.object(
            SHIRTCLAWD,
            "publish_threads_post",
            return_value={"title": "Caffeinate Hydrate Inebriate Replicate", "threads_media_id": "th123"},
        ) as publish_mock:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                SHIRTCLAWD.run_ask(args)

        append_mock.assert_called_once()
        publish_mock.assert_called_once_with(generated["posts"][0], dry_run=False)
        rendered = stdout.getvalue()
        self.assertIn("Published:", rendered)
        self.assertIn("th123", rendered)

    def test_run_ask_rejects_direct_publish_for_unsupported_platforms(self):
        inventory = [
            {
                "shirt_id": "1",
                "title": "Anything",
                "url": "https://example.com/anything",
                "image_url": "https://example.com/anything.png",
                "theme": "funny",
                "tags": ["funny"],
                "status": "available",
                "is_promotable": True,
                "promotion_status": "promote",
            }
        ]

        args = Namespace(
            prompt="Write 1 post for Facebook for Anything",
            inventory="ignored.json",
            history="history.json",
            output_dir="output",
            seed=7,
            ai_model="gpt-4o-mini",
            max_ai_calls=3,
            max_total_tokens=12000,
            max_estimated_cost=0.02,
            publish=True,
        )

        with patch.object(SHIRTCLAWD, "load_inventory", return_value=inventory), patch.object(
            SHIRTCLAWD, "load_history", return_value=[]
        ), patch.object(
            SHIRTCLAWD,
            "generate_for_platform",
            return_value={
                "posts": [{"shirt_id": "1", "title": "Anything"}],
                "destination": Path("/tmp") / "posts.json",
                "history_entries": [],
                "summary_path": Path("/tmp") / "summary.json",
            },
        ):
            with self.assertRaises(SystemExit) as raised:
                SHIRTCLAWD.run_ask(args)

        self.assertIn("Direct publish is not supported for platform 'facebook'", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
