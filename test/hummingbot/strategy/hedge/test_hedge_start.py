import unittest.mock
from decimal import Decimal

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.strategy.hedge.hedge_config_map_pydantic import EmptyMarketConfigMap, HedgeConfigMap, MarketConfigMap


class HedgeStartTest(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.strategy = None
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.client_config_map.strategy_report_interval = 60.
        self.markets = {
            "binance": ExchangeBase(client_config_map=self.client_config_map),
            "kucoin": ExchangeBase(client_config_map=self.client_config_map),
            "ascend_ex": ExchangeBase(client_config_map=self.client_config_map)
        }
        self.notifications = []
        self.log_errors = []

        config_map_raw = HedgeConfigMap(
            value_mode=True,
            hedge_ratio=Decimal("1"),
            hedge_interval=60,
            min_trade_size=Decimal("0"),
            slippage=Decimal("0.02"),
            hedge_connector="binance",
            hedge_markets=["BTC-USDT"],
            hedge_offsets=[Decimal("0.01")],
            hedge_leverage=1,
            hedge_position_mode="ONEWAY",
            connector_0=MarketConfigMap(
                connector="kucoin",
                markets=["ETH-USDT"],
                offsets=[Decimal("0.02")],
            ),
            connector_1=MarketConfigMap(
                connector="ascend_ex",
                markets=["ETH-USDT", "BTC-USDT"],
                offsets=[Decimal("0.03")],
            ),
            connector_2=EmptyMarketConfigMap(),
            connector_3=EmptyMarketConfigMap(),
            connector_4=EmptyMarketConfigMap(),

        )
        self.strategy_config_map = ClientConfigAdapter(config_map_raw)

    def _initialize_markets(self, market_names):
        pass

    def _notify(self, message):
        self.notifications.append(message)

    def logger(self):
        return self

    def error(self, message, exc_info):
        self.log_errors.append(message)
