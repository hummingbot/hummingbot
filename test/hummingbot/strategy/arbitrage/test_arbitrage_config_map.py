import unittest

from copy import deepcopy

from hummingbot.client.settings import AllConnectorSettings
from hummingbot.strategy.arbitrage.arbitrage_config_map import (
    arbitrage_config_map,
    primary_trading_pair_prompt,
    secondary_trading_pair_prompt
)


class ArbitrageConfigMapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls.primary_exchange = "binance"
        cls.secondary_exchange = "kucoin"

    def setUp(self) -> None:
        super().setUp()
        self.config_backup = deepcopy(arbitrage_config_map)

    def tearDown(self) -> None:
        self.reset_config_map()
        super().tearDown()

    def reset_config_map(self):
        for key, value in self.config_backup.items():
            arbitrage_config_map[key] = value

    def test_primary_trading_pair_prompt(self):
        arbitrage_config_map["primary_market"].value = self.primary_exchange
        example = AllConnectorSettings.get_example_pairs().get(self.primary_exchange)

        prompt = primary_trading_pair_prompt()
        expected = f"Enter the token trading pair you would like to trade on {self.primary_exchange} (e.g. {example}) >>> "

        self.assertEqual(expected, prompt)

    def test_secondary_trading_pair_prompt(self):
        arbitrage_config_map["secondary_market"].value = self.secondary_exchange
        example = AllConnectorSettings.get_example_pairs().get(self.secondary_exchange)

        prompt = secondary_trading_pair_prompt()
        expected = f"Enter the token trading pair you would like to trade on {self.secondary_exchange} (e.g. {example}) >>> "

        self.assertEqual(expected, prompt)
