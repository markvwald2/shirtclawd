import unittest

from bot.planner import build_daily_plan, determine_post_capacity, estimate_ai_post_cost_usd


class PlannerTests(unittest.TestCase):
    def test_estimate_ai_post_cost_uses_model_pricing(self):
        estimated = estimate_ai_post_cost_usd(
            pricing={"gpt-4o-mini": {"input_per_1m": 0.15, "output_per_1m": 0.6}},
            model="gpt-4o-mini",
            expected_input_tokens=1200,
            expected_output_tokens=250,
        )

        self.assertEqual(estimated, 0.00033)

    def test_determine_post_capacity_is_limited_by_platform_count(self):
        capacity = determine_post_capacity(
            platform_count=4,
            max_estimated_cost=1.0,
            estimated_ai_cost_per_post=0.00033,
        )

        self.assertEqual(capacity, 4)

    def test_build_daily_plan_prefers_less_recently_promoted_shirts(self):
        inventory = [
            {"shirt_id": "1", "title": "Alpha", "status": "available", "theme": "sports", "tags": ["sports"], "is_promotable": True, "promotion_status": "promote"},
            {"shirt_id": "2", "title": "Beta", "status": "available", "theme": "movies", "tags": ["movies"], "is_promotable": True, "promotion_status": "promote"},
            {"shirt_id": "3", "title": "Gamma", "status": "available", "theme": "funny", "tags": ["funny"], "is_promotable": True, "promotion_status": "promote"},
            {"shirt_id": "4", "title": "Delta", "status": "available", "theme": "music", "tags": ["music"], "is_promotable": True, "promotion_status": "promote"},
        ]
        history = [{"shirt_id": "1"}]

        plan = build_daily_plan(
            inventory=inventory,
            history=history,
            pricing={"gpt-4o-mini": {"input_per_1m": 0.15, "output_per_1m": 0.6}},
            ai_model="gpt-4o-mini",
            plan_date="2026-03-14",
            platforms=["x", "instagram", "facebook", "bluesky"],
            max_estimated_cost=1.0,
            approval_required=True,
        )

        self.assertEqual([post["shirt_id"] for post in plan["planned_posts"]], ["2", "4", "3", "1"])
        self.assertTrue(all(post["approval_required"] for post in plan["planned_posts"]))
        self.assertTrue(all(post["writer_mode"] == "ai" for post in plan["planned_posts"]))
        self.assertEqual(plan["planned_posts"][0]["platform"], "x")
        self.assertEqual(plan["planned_posts"][-1]["platform"], "bluesky")
        self.assertEqual(plan["writer_mode"], "ai")

    def test_build_daily_plan_can_yield_zero_posts_when_budget_covers_none(self):
        inventory = [
            {"shirt_id": "1", "title": "Alpha", "status": "available", "theme": "sports", "tags": ["sports"], "is_promotable": True, "promotion_status": "promote"},
        ]

        plan = build_daily_plan(
            inventory=inventory,
            history=[],
            pricing={"gpt-4o-mini": {"input_per_1m": 0.15, "output_per_1m": 0.6}},
            ai_model="gpt-4o-mini",
            plan_date="2026-03-14",
            platforms=["x"],
            max_estimated_cost=0.0001,
            approval_required=True,
        )

        self.assertEqual(plan["planned_posts"], [])
        self.assertEqual(plan["estimates"]["planned_capacity"], 0)


if __name__ == "__main__":
    unittest.main()
