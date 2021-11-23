from decimal import Decimal
import unittest.mock
import hummingbot.strategy.pure_market_making.start as strategy_start
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.strategy.pure_market_making.pure_market_making_config_map import (
    pure_market_making_config_map as c_map
)
from hummingbot.core.event.events import PriceType
from test.hummingbot.strategy import assign_config_default


class PureMarketMakingStartTest(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.strategy = None
        self.markets = {"binance": ExchangeBase()}
        self.notifications = []
        self.log_errors = []
        assign_config_default(c_map)
        c_map.get("exchange").value = "binance"
        c_map.get("market").value = "ETH-USDT"

        c_map.get("order_amount").value = Decimal("1")
        c_map.get("order_refresh_time").value = 60.
        c_map.get("max_order_age").value = 300.
        c_map.get("bid_spread").value = Decimal("1")
        c_map.get("ask_spread").value = Decimal("2")
        c_map.get("minimum_spread").value = Decimal("0.5")
        c_map.get("price_ceiling").value = Decimal("100")
        c_map.get("price_floor").value = Decimal("50")
        c_map.get("ping_pong_enabled").value = False
        c_map.get("order_levels").value = 2
        c_map.get("order_level_amount").value = Decimal("0.5")
        c_map.get("order_level_spread").value = Decimal("0.2")
        c_map.get("inventory_skew_enabled").value = True
        c_map.get("inventory_target_base_pct").value = Decimal("50")
        c_map.get("inventory_range_multiplier").value = Decimal("2")
        c_map.get("filled_order_delay").value = 45.
        c_map.get("hanging_orders_enabled").value = True
        c_map.get("hanging_orders_cancel_pct").value = Decimal("6")
        c_map.get("order_optimization_enabled").value = False
        c_map.get("ask_order_optimization_depth").value = Decimal("0.01")
        c_map.get("bid_order_optimization_depth").value = Decimal("0.02")
        c_map.get("add_transaction_costs").value = False
        c_map.get("price_source").value = "external_market"
        c_map.get("price_type").value = "best_bid"
        c_map.get("price_source_exchange").value = "ascend_ex"
        c_map.get("price_source_market").value = "ETH-DAI"
        c_map.get("price_source_custom_api").value = "localhost.test"
        c_map.get("order_refresh_tolerance_pct").value = Decimal("2")
        c_map.get("order_override").value = None

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
        self.assertEqual(self.strategy.order_refresh_time, 60.)
        self.assertEqual(self.strategy.max_order_age, 300.)
        self.assertEqual(self.strategy.bid_spread, Decimal("0.01"))
        self.assertEqual(self.strategy.ask_spread, Decimal("0.02"))
        self.assertEqual(self.strategy.minimum_spread, Decimal("0.005"))
        self.assertEqual(self.strategy.price_ceiling, Decimal("100"))
        self.assertEqual(self.strategy.price_floor, Decimal("50"))
        self.assertEqual(self.strategy.ping_pong_enabled, False)
        self.assertEqual(self.strategy.order_levels, 2)
        self.assertEqual(self.strategy.order_level_amount, Decimal("0.5"))
        self.assertEqual(self.strategy.order_level_spread, Decimal("0.002"))
        self.assertEqual(self.strategy.inventory_skew_enabled, True)
        self.assertEqual(self.strategy.inventory_target_base_pct, Decimal("0.5"))
        self.assertEqual(self.strategy.inventory_range_multiplier, Decimal("2"))
        self.assertEqual(self.strategy.filled_order_delay, 45.)
        self.assertEqual(self.strategy.hanging_orders_enabled, True)
        self.assertEqual(self.strategy.hanging_orders_cancel_pct, Decimal("0.06"))
        self.assertEqual(self.strategy.order_optimization_enabled, False)
        self.assertEqual(self.strategy.ask_order_optimization_depth, Decimal("0.01"))
        self.assertEqual(self.strategy.bid_order_optimization_depth, Decimal("0.02"))
        self.assertEqual(self.strategy.add_transaction_costs_to_orders, False)
        self.assertEqual(self.strategy.price_type, PriceType.BestBid)
        self.assertEqual(self.strategy.order_refresh_tolerance_pct, Decimal("0.02"))
