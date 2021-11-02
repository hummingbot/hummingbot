from decimal import Decimal
import unittest.mock
import hummingbot.strategy.spot_perpetual_arbitrage.start as strategy_start
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.strategy.spot_perpetual_arbitrage.spot_perpetual_arbitrage_config_map import (
    spot_perpetual_arbitrage_config_map as strategy_cmap
)
from test.hummingbot.strategy import assign_config_default
from test.mock.mock_perp_connector import MockPerpConnector


class SpotPerpetualArbitrageStartTest(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.strategy = None
        self.markets = {"binance": ExchangeBase(), "kucoin": MockPerpConnector()}
        self.notifications = []
        self.log_errors = []
        assign_config_default(strategy_cmap)
        strategy_cmap.get("spot_connector").value = "binance"
        strategy_cmap.get("spot_market").value = "BTC-USDT"
        strategy_cmap.get("perpetual_connector").value = "kucoin"
        strategy_cmap.get("perpetual_market").value = "BTC-USDT"

        strategy_cmap.get("order_amount").value = Decimal("1")
        strategy_cmap.get("perpetual_leverage").value = Decimal("2")
        strategy_cmap.get("min_opening_arbitrage_pct").value = Decimal("10")
        strategy_cmap.get("min_closing_arbitrage_pct").value = Decimal("1")

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
        self.assertEqual(self.strategy._order_amount, Decimal("1"))
        self.assertEqual(self.strategy._perp_leverage, Decimal("2"))
        self.assertEqual(self.strategy._min_opening_arbitrage_pct, Decimal("0.1"))
        self.assertEqual(self.strategy._min_closing_arbitrage_pct, Decimal("0.01"))
