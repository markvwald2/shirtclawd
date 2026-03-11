import unittest

from bot.selector import select_shirts


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


if __name__ == "__main__":
    unittest.main()
