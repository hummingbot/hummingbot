import unittest.mock
from decimal import Decimal

import hummingbot.strategy.cross_exchange_market_making.start as strategy_start
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.strategy.cross_exchange_market_making.cross_exchange_market_making_config_map_pydantic import (
    CrossExchangeMarketMakingConfigMap,
)


class XEMMStartTest(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.strategy = None
        self.markets = {"binance": ExchangeBase(), "kucoin": ExchangeBase()}
        self.notifications = []
        self.log_errors = []

        self.strategy_config_map = ClientConfigAdapter(
            CrossExchangeMarketMakingConfigMap(
                market_maker="binance",
                market_taker="kucoin",
                trading_pair_maker="ETH-USDT",
                trading_pair_taker="ETH-USDT",
                order_amount=1.0,
                min_profitability=2.0,
                use_oracle_conversion_rate=False,
            )
        )

        global_config_map.get("strategy_report_interval").value = 60.

    def _initialize_market_assets(self, market, trading_pairs):
        return [("ETH", "USDT")]

    def _initialize_markets(self, market_names):
        pass

    def _notify(self, message):
        self.notifications.append(message)

    def logger(self):
        return self

    def error(self, message, exc_info):
        self.log_errors.append(message)

    def test_strategy_creation(self):
        strategy_start.start(self)
        self.assertEqual(self.strategy.order_amount, Decimal("1"))
        self.assertEqual(self.strategy.min_profitability, Decimal("0.02"))
