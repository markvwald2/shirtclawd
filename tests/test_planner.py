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

    def test_build_daily_plan_can_target_coloradans_against_campaign(self):
        inventory = [
            {"shirt_id": "1", "title": "Coloradans Against Craft Beer", "status": "available", "theme": "Coloradans Against", "tags": ["colorado", "beer"], "is_promotable": True, "promotion_status": "promote"},
            {"shirt_id": "2", "title": "Coloradans Against Hiking", "status": "available", "theme": "Coloradans Against", "tags": ["colorado", "hiking"], "is_promotable": True, "promotion_status": "promote"},
            {"shirt_id": "3", "title": "Ski in your Jeans", "status": "available", "theme": "skiing", "tags": ["ski"], "is_promotable": True, "promotion_status": "promote"},
        ]

        plan = build_daily_plan(
            inventory=inventory,
            history=[],
            pricing={"gpt-4o-mini": {"input_per_1m": 0.15, "output_per_1m": 0.6}},
            ai_model="gpt-4o-mini",
            plan_date="2026-03-14",
            platforms=["instagram", "bluesky"],
            max_estimated_cost=1.0,
            approval_required=False,
            campaign="coloradans_against",
        )

        self.assertEqual(plan["campaign"], "coloradans_against")
        self.assertEqual([post["shirt_id"] for post in plan["planned_posts"]], ["1", "2"])
        self.assertTrue(all(post["campaign"] == "coloradans_against" for post in plan["planned_posts"]))
        self.assertTrue(all(post["series"] == "Coloradans Against" for post in plan["planned_posts"]))
        self.assertEqual(plan["planned_posts"][0]["content_goal"], "conversation")
        self.assertEqual(plan["planned_posts"][0]["cta_goal"], "reply")
        self.assertEqual(plan["planned_posts"][1]["content_format"], "pick_your_enemy")
        self.assertTrue(all(post["active_offer"] == "20% off all Spreadshirt orders" for post in plan["planned_posts"]))
        self.assertTrue(all(post["offer_starts_on"] == "2026-05-15" for post in plan["planned_posts"]))
        self.assertTrue(all(post["offer_ends_on"] == "2026-05-19" for post in plan["planned_posts"]))
        self.assertTrue(all(post["secondary_offer"] == "" for post in plan["planned_posts"]))

    def test_build_daily_plan_can_add_coloradans_against_set_post(self):
        inventory = [
            {"shirt_id": "1", "title": "Coloradans Against Craft Beer", "status": "available", "theme": "Coloradans Against", "tags": ["colorado", "beer"], "is_promotable": True, "promotion_status": "promote"},
            {"shirt_id": "2", "title": "Coloradans Against Hiking", "status": "available", "theme": "Coloradans Against", "tags": ["colorado", "hiking"], "is_promotable": True, "promotion_status": "promote"},
            {"shirt_id": "3", "title": "Coloradans Against Triathlons", "status": "available", "theme": "Coloradans Against", "tags": ["colorado", "triathlon"], "is_promotable": True, "promotion_status": "promote"},
            {"shirt_id": "4", "title": "Coloradans Against Fourteeners", "status": "available", "theme": "Coloradans Against", "tags": ["colorado", "fourteeners"], "is_promotable": True, "promotion_status": "promote"},
        ]

        plan = build_daily_plan(
            inventory=inventory,
            history=[],
            pricing={"gpt-4o-mini": {"input_per_1m": 0.15, "output_per_1m": 0.6}},
            ai_model="gpt-4o-mini",
            plan_date="2026-03-14",
            platforms=["bluesky", "instagram", "facebook", "threads"],
            max_estimated_cost=1.0,
            approval_required=False,
            campaign="coloradans_against",
            include_campaign_set_post=True,
        )

        self.assertEqual(len(plan["planned_posts"]), 8)
        set_posts = plan["planned_posts"][-4:]
        self.assertEqual([post["platform"] for post in set_posts], ["bluesky", "instagram", "facebook", "threads"])
        self.assertTrue(all(post["post_kind"] == "series_set" for post in set_posts))
        self.assertTrue(all(post["content_format"] == "series_set" for post in set_posts))
        self.assertTrue(all(post["shirt_ids"] == ["1", "4", "2", "3"] for post in set_posts))
        self.assertTrue(all(post["collection_size"] == 4 for post in set_posts))
        self.assertEqual(plan["estimates"]["estimated_total_ai_cost_usd"], 0.00264)


if __name__ == "__main__":
    unittest.main()
