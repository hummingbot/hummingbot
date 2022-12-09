import unittest

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.client.ui.layout import get_active_strategy, get_strategy_file


class LayoutTest(unittest.TestCase):

    def test_get_active_strategy(self):
        hb = HummingbotApplication.main_application()
        hb.strategy_name = "SomeStrategy"
        res = get_active_strategy()
        style, text = res[0]

        self.assertEqual("class:log_field", style)
        self.assertEqual(f"Strategy: {hb.strategy_name}", text)

    def test_get_strategy_file(self):
        hb = HummingbotApplication.main_application()
        hb._strategy_file_name = "some_strategy.yml"
        res = get_strategy_file()
        style, text = res[0]

        self.assertEqual("class:log_field", style)
        self.assertEqual(f"Strategy File: {hb._strategy_file_name}", text)
