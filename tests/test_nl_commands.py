import unittest

from bot.nl_commands import parse_command


class NaturalLanguageCommandTests(unittest.TestCase):
    def test_parse_generation_command_with_platform_count_and_query(self):
        command = parse_command("Write 2 posts for Instagram for the Coloradans Against shirts")

        self.assertEqual(command.action, "generate")
        self.assertEqual(command.platform, "instagram")
        self.assertEqual(command.count, 2)
        self.assertEqual(command.query, "coloradans against shirts")

    def test_parse_generation_command_defaults_to_single_post(self):
        command = parse_command("Generate a post for Bluesky about the ski shirts")

        self.assertEqual(command.platform, "bluesky")
        self.assertEqual(command.count, 1)
        self.assertEqual(command.query, "ski shirts")

    def test_parse_generation_command_requires_supported_platform(self):
        with self.assertRaises(ValueError):
            parse_command("Write 2 posts for Mastodon for the funny shirts")


if __name__ == "__main__":
    unittest.main()
