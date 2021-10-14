import unittest
from copy import deepcopy

from hummingbot.strategy.avellaneda_market_making.avellaneda_market_making_config_map import (
    avellaneda_market_making_config_map,
    order_amount_prompt,
)


class AvellanedaMarketMakingConfigMapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.config_backup = deepcopy(avellaneda_market_making_config_map)

    def tearDown(self) -> None:
        self.reset_config_map()
        super().tearDown()

    def reset_config_map(self):
        for key, value in self.config_backup.items():
            avellaneda_market_making_config_map[key] = value

    def test_order_amount_prompt(self):
        avellaneda_market_making_config_map["market"].value = self.trading_pair
        prompt = order_amount_prompt()
        expected = f"What is the amount of {self.base_asset} per order? >>> "

        self.assertEqual(expected, prompt)
