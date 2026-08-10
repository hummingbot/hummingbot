import unittest

from kairos.client.kairos_application import KairosApplication
from kairos.client.ui.layout import get_active_strategy, get_strategy_file


class LayoutTest(unittest.TestCase):

    def test_get_active_strategy(self):
        hb = KairosApplication.main_application()
        hb.trading_core.strategy_name = "SomeStrategy"
        res = get_active_strategy()
        style, text = res[0]

        self.assertEqual("class:log_field", style)
        self.assertEqual(f"Strategy: {hb.strategy_name}", text)

    def test_get_strategy_file(self):
        hb = KairosApplication.main_application()
        hb.strategy_file_name = "some_strategy.yml"
        res = get_strategy_file()
        style, text = res[0]

        self.assertEqual("class:log_field", style)
        self.assertEqual(f"Strategy File: {hb.strategy_file_name}", text)
