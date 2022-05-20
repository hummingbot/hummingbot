import unittest
from typing import Dict

from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.strategy.cross_exchange_market_making.cross_exchange_market_making_config_map_pydantic import (
    CrossExchangeMarketMakingConfigMap,
)


class CrossExchangeMarketMakingConfigMapPydanticTest(unittest.TestCase):
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
        config_settings = self.get_default_map()
        self.config_map = ClientConfigAdapter(CrossExchangeMarketMakingConfigMap(**config_settings))

    def get_default_map(self) -> Dict[str, str]:
        config_settings = {
            "maker_market": self.maker_exchange,
            "taker_market": self.taker_exchange,
            "maker_market_trading_pair": self.trading_pair,
            "taker_market_trading_pair": self.trading_pair,
            "order_amount": "10",
            "min_profitability": "0",
        }
        return config_settings

    def test_order_amount_prompt(self):
        self.config_map.maker_market_trading_pair = self.trading_pair
        prompt = self.config_map.order_amount_prompt(self.config_map)
        expected = f"What is the amount of {self.base_asset} per order?"

        self.assertEqual(expected, prompt)

    def test_maker_trading_pair_prompt(self):
        exchange = self.config_map.maker_market = self.maker_exchange
        example = AllConnectorSettings.get_example_pairs().get(exchange)

        prompt = self.config_map.trading_pair_prompt(self.config_map, True)
        expected = f"Enter the token trading pair you would like to trade on maker market: {exchange} " \
                   f"(e.g. {example})"

        self.assertEqual(expected, prompt)

    def test_taker_trading_pair_prompt(self):
        exchange = self.config_map.maker_market = self.taker_exchange
        example = AllConnectorSettings.get_example_pairs().get(exchange)

        prompt = self.config_map.trading_pair_prompt(self.config_map, False)
        expected = f"Enter the token trading pair you would like to trade on taker market: {exchange} " \
                   f"(e.g. {example})"

        self.assertEqual(expected, prompt)
