import unittest

from copy import deepcopy

from hummingbot.client.settings import AllConnectorSettings
from hummingbot.strategy.dev_1_get_order_book.dev_1_get_order_book_config_map import (
    dev_1_get_order_book_config_map,
    trading_pair_prompt,
)


class Dev1GetOrderBookConfigMapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls.exchange = "binance"

    def setUp(self) -> None:
        super().setUp()
        self.config_backup = deepcopy(dev_1_get_order_book_config_map)

    def tearDown(self) -> None:
        self.reset_config_map()
        super().tearDown()

    def reset_config_map(self):
        for key, value in self.config_backup.items():
            dev_1_get_order_book_config_map[key] = value

    def test_trading_pair_prompt(self):
        dev_1_get_order_book_config_map["exchange"].value = self.exchange
        example = AllConnectorSettings.get_example_pairs().get(self.exchange)

        prompt = trading_pair_prompt()
        expected = f"Enter the token trading pair to fetch its order book on {self.exchange} (e.g. {example}) >>> "

        self.assertEqual(expected, prompt)
