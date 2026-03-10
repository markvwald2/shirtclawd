import unittest

from bot.selector import select_shirts


class SelectorTests(unittest.TestCase):
    def test_select_shirts_prefers_unpromoted_items_and_theme_variety(self):
        inventory = [
            {"shirt_id": "1", "title": "Alpha", "status": "available", "theme": "sports", "tags": ["sports"]},
            {"shirt_id": "2", "title": "Beta", "status": "available", "theme": "movies", "tags": ["movies"]},
            {"shirt_id": "3", "title": "Gamma", "status": "available", "theme": "sports", "tags": ["sports"]},
        ]
        history = [{"shirt_id": "1"}]

        selected = select_shirts(inventory, history, 2)

        self.assertEqual([shirt["shirt_id"] for shirt in selected], ["2", "3"])


if __name__ == "__main__":
    unittest.main()
