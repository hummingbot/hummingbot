import unittest

from copy import deepcopy

from hummingbot.client.settings import AllConnectorSettings
from hummingbot.strategy.dev_5_vwap.dev_5_vwap_config_map import (
    dev_5_vwap_config_map,
    order_percent_of_volume_prompt,
    symbol_prompt,
)


class VwapConfigMapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls.exchange = "binance"

    def setUp(self) -> None:
        super().setUp()
        self.config_backup = deepcopy(dev_5_vwap_config_map)

    def tearDown(self) -> None:
        self.reset_config_map()
        super().tearDown()

    def reset_config_map(self):
        for key, value in self.config_backup.items():
            dev_5_vwap_config_map[key] = value

    def test_symbol_prompt(self):
        dev_5_vwap_config_map["exchange"].value = self.exchange
        example = AllConnectorSettings.get_example_pairs().get(self.exchange)

        prompt = symbol_prompt()
        expected = f"Enter the trading pair you would like to trade on {self.exchange} (e.g. {example}) >>> "

        self.assertEqual(expected, prompt)

    def test_order_percent_of_volume_prompt(self):
        dev_5_vwap_config_map["percent_slippage"].value = 1
        prompt = order_percent_of_volume_prompt()
        expected = f"What percent of open order volume up to {1} percent slippage do you want each order to be? (default is 100 percent)? >>> "

        self.assertEqual(expected, prompt)
