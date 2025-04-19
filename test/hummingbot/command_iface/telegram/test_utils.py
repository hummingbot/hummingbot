from unittest import TestCase

from hummingbot.command_iface.telegram.constants import TELEGRAM_MAX_MESSAGE_LENGTH
from hummingbot.command_iface.telegram.utils import split_message


class TestTelegramUtils(TestCase):
    def test_split_short_message(self):
        """Test splitting short message that fits in one part"""
        message = "Short message"
        parts = split_message(message)
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0], message)

    def test_split_long_message(self):
        """Test splitting long message into parts"""
        message = "x" * (TELEGRAM_MAX_MESSAGE_LENGTH + 100)
        parts = split_message(message)

        self.assertGreater(len(parts), 1)
        for part in parts:
            self.assertLessEqual(len(part), TELEGRAM_MAX_MESSAGE_LENGTH)

    def test_split_preserve_newlines(self):
        """Test splitting preserves newline formatting"""
        message = "Line 1\nLine 2\nLine 3"
        parts = split_message(message)

        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].count("\n"), 2)

    def test_split_message_with_long_lines(self):
        """Test splitting message with lines longer than max length"""
        long_line = "x" * (TELEGRAM_MAX_MESSAGE_LENGTH + 100)
        message = f"Short line\n{long_line}\nAnother short line"
        parts = split_message(message)

        self.assertGreater(len(parts), 1)
        self.assertTrue(any("Short line" in part for part in parts))
        self.assertTrue(any("Another short line" in part for part in parts))

    def test_split_empty_message(self):
        """Test splitting empty message"""
        message = ""
        parts = split_message(message)

        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0], "")
