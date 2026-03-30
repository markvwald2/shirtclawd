import unittest

from bot.usage_logger import (
    build_run_summary,
    build_usage_event,
    budget_status,
    create_run_context,
    estimate_cost_usd,
    update_budget_state,
)


class UsageLoggerTests(unittest.TestCase):
    def test_estimate_cost_uses_cached_and_uncached_rates(self):
        usage = {
            "input_tokens": 1000,
            "output_tokens": 500,
            "input_tokens_details": {"cached_tokens": 200},
        }
        pricing = {
            "input_per_1m": 1.0,
            "cached_input_per_1m": 0.5,
            "output_per_1m": 2.0,
        }

        cost = estimate_cost_usd(usage, pricing)

        self.assertAlmostEqual(cost, 0.0019)

    def test_build_run_summary_counts_errors_without_fallbacks(self):
        run_context = create_run_context("x", "ai", "gpt-4o-mini", 2)
        posts = [{"writer_mode": "ai", "post_type": "ai_custom"}]
        events = [
            build_usage_event(
                run_context=run_context,
                shirt={"shirt_id": "1", "title": "Test"},
                platform="x",
                model="gpt-4o-mini",
                writer_mode="ai",
                status="error",
                error="OPENAI_API_KEY is not set.",
            )
        ]

        summary = build_run_summary(run_context, posts, events)

        self.assertEqual(summary["ai_fallbacks"], 0)
        self.assertEqual(summary["ai_errors"], 1)
        self.assertEqual(summary["posts_by_writer_mode"]["ai"], 1)

    def test_budget_status_trips_after_successful_ai_call(self):
        run_context = create_run_context("x", "ai", "gpt-4o-mini", 2, max_ai_calls=1)
        event = build_usage_event(
            run_context=run_context,
            shirt={"shirt_id": "1", "title": "Test"},
            platform="x",
            model="gpt-4o-mini",
            writer_mode="ai",
            status="success",
            usage={"total_tokens": 50},
        )

        update_budget_state(run_context, event)

        self.assertEqual(budget_status(run_context), "max_ai_calls=1")


if __name__ == "__main__":
    unittest.main()
