import unittest
from copy import deepcopy

from hummingbot.client.settings import AllConnectorSettings
from hummingbot.strategy.cross_exchange_market_making.cross_exchange_market_making_config_map import (
    cross_exchange_market_making_config_map,
    order_amount_prompt,
    maker_trading_pair_prompt,
    taker_trading_pair_prompt
)


class CrossExchangeMarketMakingConfigMapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

        cls.maker_exchange = "binance"
        cls.taker_exchange = "kucoin"

    def setUp(self) -> None:
        super().setUp()
        self.config_backup = deepcopy(cross_exchange_market_making_config_map)

    def tearDown(self) -> None:
        self.reset_config_map()
        super().tearDown()

    def reset_config_map(self):
        for key, value in self.config_backup.items():
            cross_exchange_market_making_config_map[key] = value

    def test_order_amount_prompt(self):
        cross_exchange_market_making_config_map["maker_market_trading_pair"].value = self.trading_pair
        prompt = order_amount_prompt()
        expected = f"What is the amount of {self.base_asset} per order? >>> "

        self.assertEqual(expected, prompt)

    def test_maker_trading_pair_prompt(self):
        exchange = cross_exchange_market_making_config_map["maker_market"].value = self.maker_exchange
        example = AllConnectorSettings.get_example_pairs().get(exchange)

        prompt = maker_trading_pair_prompt()
        expected = f"Enter the token trading pair you would like to trade on maker market: {exchange} " \
                   f"(e.g. {example}) >>> "

        self.assertEqual(expected, prompt)

    def test_taker_trading_pair_prompt(self):
        exchange = cross_exchange_market_making_config_map["taker_market"].value = self.taker_exchange
        example = AllConnectorSettings.get_example_pairs().get(exchange)

        prompt = taker_trading_pair_prompt()
        expected = f"Enter the token trading pair you would like to trade on taker market: {exchange} " \
                   f"(e.g. {example}) >>> "

        self.assertEqual(expected, prompt)
