import unittest

from bot.selector import select_matching_shirts, select_shirts


class SelectorTests(unittest.TestCase):
    def test_select_shirts_prefers_unpromoted_items_and_theme_variety(self):
        inventory = [
            {"shirt_id": "1", "title": "Alpha", "status": "available", "theme": "sports", "tags": ["sports"], "is_promotable": True, "promotion_status": "promote"},
            {"shirt_id": "2", "title": "Beta", "status": "available", "theme": "movies", "tags": ["movies"], "is_promotable": True, "promotion_status": "promote"},
            {"shirt_id": "3", "title": "Gamma", "status": "available", "theme": "sports", "tags": ["sports"], "is_promotable": True, "promotion_status": "promote"},
        ]
        history = [{"shirt_id": "1"}]

        selected = select_shirts(inventory, history, 2)

        self.assertEqual([shirt["shirt_id"] for shirt in selected], ["2", "3"])

    def test_select_shirts_skips_non_promotable_inventory(self):
        inventory = [
            {"shirt_id": "1", "title": "Alpha", "status": "available", "theme": "sports", "tags": ["sports"], "is_promotable": False, "promotion_status": "review"},
            {"shirt_id": "2", "title": "Beta", "status": "available", "theme": "movies", "tags": ["movies"], "promotion_status": "skip"},
            {"shirt_id": "3", "title": "Gamma", "status": "available", "theme": "sports", "tags": ["sports"], "is_promotable": True, "promotion_status": "promote"},
        ]

        selected = select_shirts(inventory, [], 3)

        self.assertEqual([shirt["shirt_id"] for shirt in selected], ["3"])

    def test_select_shirts_excludes_unannotated_default_review_items(self):
        inventory = [
            {"shirt_id": "1", "title": "Alpha", "status": "available", "theme": "sports", "tags": ["sports"], "is_promotable": False, "promotion_status": "review"},
            {"shirt_id": "2", "title": "Beta", "status": "available", "theme": "movies", "tags": ["movies"], "is_promotable": True, "promotion_status": "promote"},
        ]

        selected = select_shirts(inventory, [], 2)

        self.assertEqual([shirt["shirt_id"] for shirt in selected], ["2"])

    def test_select_shirts_deprioritizes_recently_posted_designs(self):
        inventory = [
            {"shirt_id": "1", "title": "Alpha", "status": "available", "theme": "sports", "tags": ["sports"], "is_promotable": True, "promotion_status": "promote"},
            {"shirt_id": "2", "title": "Beta", "status": "available", "theme": "movies", "tags": ["movies"], "is_promotable": True, "promotion_status": "promote"},
            {"shirt_id": "3", "title": "Gamma", "status": "available", "theme": "funny", "tags": ["funny"], "is_promotable": True, "promotion_status": "promote"},
        ]
        history = [{"shirt_id": "3"}, {"shirt_id": "2"}]

        selected = select_shirts(inventory, history, 1)

        self.assertEqual([shirt["shirt_id"] for shirt in selected], ["1"])

    def test_select_shirts_deprioritizes_recent_themes_when_possible(self):
        inventory = [
            {"shirt_id": "1", "title": "Alpha", "status": "available", "theme": "sports", "tags": ["sports"], "is_promotable": True, "promotion_status": "promote"},
            {"shirt_id": "2", "title": "Beta", "status": "available", "theme": "sports", "tags": ["sports"], "is_promotable": True, "promotion_status": "promote"},
            {"shirt_id": "3", "title": "Gamma", "status": "available", "theme": "movies", "tags": ["movies"], "is_promotable": True, "promotion_status": "promote"},
        ]
        history = [{"shirt_id": "1"}]

        selected = select_shirts(inventory, history, 1)

        self.assertEqual([shirt["shirt_id"] for shirt in selected], ["3"])

    def test_select_matching_shirts_filters_by_theme_and_title_tokens(self):
        inventory = [
            {"shirt_id": "1", "title": "Coloradans Against Craft Beer", "status": "available", "theme": "Coloradans Against", "tags": ["colorado", "beer"], "is_promotable": True, "promotion_status": "promote"},
            {"shirt_id": "2", "title": "Coloradans Against Hiking", "status": "available", "theme": "Coloradans Against", "tags": ["colorado", "hiking"], "is_promotable": True, "promotion_status": "promote"},
            {"shirt_id": "3", "title": "Ski in your Jeans", "status": "available", "theme": "skiing", "tags": ["ski"], "is_promotable": True, "promotion_status": "promote"},
        ]

        selected = select_matching_shirts(inventory, [], 2, "coloradans against shirts")

        self.assertEqual([shirt["shirt_id"] for shirt in selected], ["1", "2"])

    def test_select_matching_shirts_returns_empty_when_no_matches(self):
        inventory = [
            {"shirt_id": "1", "title": "Coloradans Against Craft Beer", "status": "available", "theme": "Coloradans Against", "tags": ["colorado", "beer"], "is_promotable": True, "promotion_status": "promote"},
        ]

        selected = select_matching_shirts(inventory, [], 2, "movie shirts")

        self.assertEqual(selected, [])


if __name__ == "__main__":
    unittest.main()
