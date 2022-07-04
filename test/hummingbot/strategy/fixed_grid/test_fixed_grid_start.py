import unittest.mock
from decimal import Decimal
from test.hummingbot.strategy import assign_config_default

import hummingbot.strategy.fixed_grid.start as strategy_start
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.strategy.fixed_grid.fixed_grid_config_map import fixed_grid_config_map as c_map


class FixedGridStartTest(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.strategy = None
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.markets = {"binance": ExchangeBase(client_config_map=self.client_config_map)}
        self.notifications = []
        self.log_errors = []
        assign_config_default(c_map)
        c_map.get("exchange").value = "binance"
        c_map.get("market").value = "ETH-USDT"

        c_map.get("n_levels").value = 10
        c_map.get("grid_price_ceiling").value = Decimal("5000")
        c_map.get("grid_price_floor").value = Decimal("2000")
        c_map.get("start_order_spread").value = Decimal("1")
        c_map.get("order_refresh_time").value = 60.
        c_map.get("max_order_age").value = 300.
        c_map.get("order_refresh_tolerance_pct").value = Decimal("2")
        c_map.get("order_amount").value = Decimal("1")
        c_map.get("order_optimization_enabled").value = False
        c_map.get("ask_order_optimization_depth").value = Decimal("0.01")
        c_map.get("bid_order_optimization_depth").value = Decimal("0.02")

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
        self.assertEqual(self.strategy.n_levels, 10)
        self.assertEqual(self.strategy.grid_price_ceiling, Decimal("5000"))
        self.assertEqual(self.strategy.grid_price_floor, Decimal("2000"))
        self.assertEqual(self.strategy.start_order_spread, Decimal("0.01"))
        self.assertEqual(self.strategy.order_refresh_time, 60.)
        self.assertEqual(self.strategy.max_order_age, 300.)
        self.assertEqual(self.strategy.order_refresh_tolerance_pct, Decimal("0.02"))
        self.assertEqual(self.strategy.order_amount, Decimal("1"))
        self.assertEqual(self.strategy.order_optimization_enabled, False)
        self.assertEqual(self.strategy.ask_order_optimization_depth, Decimal("0.01"))
        self.assertEqual(self.strategy.bid_order_optimization_depth, Decimal("0.02"))
