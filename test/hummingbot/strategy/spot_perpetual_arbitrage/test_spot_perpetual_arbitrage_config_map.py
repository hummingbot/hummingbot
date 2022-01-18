import unittest

from copy import deepcopy

from hummingbot.client.settings import AllConnectorSettings
from hummingbot.strategy.spot_perpetual_arbitrage.spot_perpetual_arbitrage_config_map import (
    spot_perpetual_arbitrage_config_map,
    spot_market_prompt,
    perpetual_market_prompt,
)


class SpotPerpetualArbitrageConfigMapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls.spot_exchange = "binance"
        cls.perp_exchange = "binance_perpetual"

    def setUp(self) -> None:
        super().setUp()
        self.config_backup = deepcopy(spot_perpetual_arbitrage_config_map)

    def tearDown(self) -> None:
        self.reset_config_map()
        super().tearDown()

    def reset_config_map(self):
        for key, value in self.config_backup.items():
            spot_perpetual_arbitrage_config_map[key] = value

    def test_spot_market_prompt(self):
        spot_perpetual_arbitrage_config_map["spot_connector"].value = self.spot_exchange
        example = AllConnectorSettings.get_example_pairs().get(self.spot_exchange)

        prompt = spot_market_prompt()
        expected = f"Enter the token trading pair you would like to trade on {self.spot_exchange} (e.g. {example}) >>> "

        self.assertEqual(expected, prompt)

    def test_perpetual_market_prompt(self):
        spot_perpetual_arbitrage_config_map["perpetual_connector"].value = self.perp_exchange
        example = AllConnectorSettings.get_example_pairs().get(self.perp_exchange)

        prompt = perpetual_market_prompt()
        expected = f"Enter the token trading pair you would like to trade on {self.perp_exchange} (e.g. {example}) >>> "

        self.assertEqual(expected, prompt)
