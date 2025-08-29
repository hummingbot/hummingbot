from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase

import hummingbot.strategy.cross_exchange_market_making.start as strategy_start
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.strategy.cross_exchange_market_making.cross_exchange_market_making_config_map_pydantic import (
    CrossExchangeMarketMakingConfigMap,
    TakerToMakerConversionRateMode,
)


class XEMMStartTest(IsolatedAsyncioWrapperTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.strategy = None
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.client_config_map.strategy_report_interval = 60.
        self.markets = {
            "binance": ExchangeBase(),
            "kucoin": ExchangeBase()}
        self.notifications = []
        self.log_errors = []

        config_map_raw = CrossExchangeMarketMakingConfigMap(
            maker_market="binance",
            taker_market="kucoin",
            maker_market_trading_pair="ETH-USDT",
            taker_market_trading_pair="ETH-USDT",
            order_amount=1.0,
            min_profitability=2.0,
            conversion_rate_mode=TakerToMakerConversionRateMode(),
        )

        config_map_raw.conversion_rate_mode.taker_to_maker_base_conversion_rate = Decimal("1.0")
        config_map_raw.conversion_rate_mode.taker_to_maker_quote_conversion_rate = Decimal("1.0")

        self.strategy_config_map = ClientConfigAdapter(config_map_raw)

    def _initialize_market_assets(self, market, trading_pairs):
        return [("ETH", "USDT")]

    async def initialize_markets(self, market_names):
        pass

    def _notify(self, message):
        self.notifications.append(message)

    def logger(self):
        return self

    def error(self, message, exc_info):
        self.log_errors.append(message)

    async def test_strategy_creation(self):
        await strategy_start.start(self)
        self.assertEqual(self.strategy.order_amount, Decimal("1"))
        self.assertEqual(self.strategy.min_profitability, Decimal("0.02"))
