import unittest

from copy import deepcopy

from hummingbot.client.settings import AllConnectorSettings
from hummingbot.strategy.uniswap_v3_lp.uniswap_v3_lp_config_map import (
    uniswap_v3_lp_config_map,
    market_prompt,
)


class SpotPerpetualArbitrageConfigMapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls.spot_exchange = "binance"
        cls.perp_exchange = "binance_perpetual"

    def setUp(self) -> None:
        super().setUp()
        self.config_backup = deepcopy(uniswap_v3_lp_config_map)

    def tearDown(self) -> None:
        self.reset_config_map()
        super().tearDown()

    def reset_config_map(self):
        for key, value in self.config_backup.items():
            uniswap_v3_lp_config_map[key] = value

    def test_market_prompt(self):
        example = AllConnectorSettings.get_example_pairs().get("uniswap_v3")

        prompt = market_prompt()
        expected = f"Enter the trading pair you would like to provide liquidity on (e.g. {example}) >>> "

        self.assertEqual(expected, prompt)
