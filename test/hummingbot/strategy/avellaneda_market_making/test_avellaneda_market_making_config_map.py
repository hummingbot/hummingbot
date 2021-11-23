import unittest
from copy import deepcopy

from hummingbot.client.settings import AllConnectorSettings
from hummingbot.strategy.avellaneda_market_making.avellaneda_market_making_config_map import (
    avellaneda_market_making_config_map,
    maker_trading_pair_prompt,
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

    def test_maker_trading_pair_prompt(self):
        exchange = avellaneda_market_making_config_map["exchange"].value = "binance"
        example = AllConnectorSettings.get_example_pairs().get(exchange)

        prompt = maker_trading_pair_prompt()
        expected = f"Enter the token trading pair you would like to trade on {exchange} (e.g. {example}) >>> "

        self.assertEqual(expected, prompt)
