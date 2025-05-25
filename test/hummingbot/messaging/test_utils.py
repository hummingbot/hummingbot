import unittest

from hummingbot.messaging.utils import format_composite_id_for_display


class MessagingUtilsTest(unittest.TestCase):
    def test_format_composite_id_full_format(self):
        """Test formatting a composite ID with instance ID and strategy file"""
        composite_id = "instance_12345678|strategy_file"
        formatted = format_composite_id_for_display(composite_id)
        self.assertEqual(formatted, "instance|strategy_file")

    def test_format_composite_id_long_instance(self):
        """Test formatting a composite ID with a very long instance ID"""
        composite_id = "very_long_instance_id_that_should_be_truncated|strategy"
        formatted = format_composite_id_for_display(composite_id)
        self.assertEqual(formatted, "very_lon|strategy")

    def test_format_composite_id_no_separator(self):
        """Test formatting a string without the separator"""
        text = "instance_without_separator"
        formatted = format_composite_id_for_display(text)
        self.assertEqual(formatted, "instance_without_separator")

    def test_format_composite_id_empty_parts(self):
        """Test formatting a composite ID with empty parts"""
        composite_id = "|strategy"
        formatted = format_composite_id_for_display(composite_id)
        self.assertEqual(formatted, "|strategy")

    def test_format_composite_id_multiple_separators(self):
        """Test formatting a composite ID with multiple separators"""
        composite_id = "instance|strategy|extra"
        formatted = format_composite_id_for_display(composite_id)
        self.assertEqual(formatted, "instance|strategy|extra")


if __name__ == "__main__":
    unittest.main()
