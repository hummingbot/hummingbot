from decimal import Decimal
import unittest.mock
import hummingbot.strategy.liquidity_mining.start as strategy_start
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.strategy.liquidity_mining.liquidity_mining_config_map import (
    liquidity_mining_config_map as strategy_cmap
)
from test.hummingbot.strategy import assign_config_default


class LiquidityMiningStartTest(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.strategy = None
        self.markets = {"binance": ExchangeBase()}
        self.notifications = []
        self.log_errors = []
        assign_config_default(strategy_cmap)
        strategy_cmap.get("exchange").value = "binance"
        strategy_cmap.get("markets").value = "BTC-USDT,ETH-USDT"
        strategy_cmap.get("token").value = "USDT"
        strategy_cmap.get("order_amount").value = Decimal("1")
        strategy_cmap.get("spread").value = Decimal("2")

        strategy_cmap.get("inventory_skew_enabled").value = False
        strategy_cmap.get("target_base_pct").value = Decimal("50")
        strategy_cmap.get("order_refresh_time").value = 60.
        strategy_cmap.get("order_refresh_tolerance_pct").value = Decimal("1.5")
        strategy_cmap.get("inventory_range_multiplier").value = Decimal("2")
        strategy_cmap.get("volatility_interval").value = 30
        strategy_cmap.get("avg_volatility_period").value = 5
        strategy_cmap.get("volatility_to_spread_multiplier").value = Decimal("1.1")
        strategy_cmap.get("max_spread").value = Decimal("4")
        strategy_cmap.get("max_order_age").value = 300.

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
        self.assertEqual(self.strategy._spread, Decimal("0.02"))

        self.assertEqual(self.strategy._inventory_skew_enabled, False)
        self.assertEqual(self.strategy._target_base_pct, Decimal("0.5"))
        self.assertEqual(self.strategy._order_refresh_time, 60.)
        self.assertEqual(self.strategy._order_refresh_tolerance_pct, Decimal("0.015"))
        self.assertEqual(self.strategy._inventory_range_multiplier, Decimal("2"))
        self.assertEqual(self.strategy._volatility_interval, 30)
        self.assertEqual(self.strategy._avg_volatility_period, 5)
        self.assertEqual(self.strategy._volatility_to_spread_multiplier, Decimal("1.1"))
        self.assertEqual(self.strategy._max_spread, Decimal("0.04"))
        self.assertEqual(self.strategy._max_order_age, 300.)
