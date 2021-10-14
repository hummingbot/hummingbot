import unittest
from copy import deepcopy

from hummingbot.strategy.dev_2_perform_trade.dev_2_perform_trade_config_map import (
    dev_2_perform_trade_config_map,
    order_amount_prompt,
)


class Dev2PerformTradeConfigMapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.config_backup = deepcopy(dev_2_perform_trade_config_map)

    def tearDown(self) -> None:
        self.reset_config_map()
        super().tearDown()

    def reset_config_map(self):
        for key, value in self.config_backup.items():
            dev_2_perform_trade_config_map[key] = value

    def test_order_amount_prompt(self):
        dev_2_perform_trade_config_map["trading_pair"].value = self.trading_pair
        prompt = order_amount_prompt()
        expected = f"What is the amount of {self.base_asset} per order? >>> "

        self.assertEqual(expected, prompt)
