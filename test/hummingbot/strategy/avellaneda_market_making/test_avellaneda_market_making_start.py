import datetime
from decimal import Decimal
import unittest.mock
import hummingbot.strategy.avellaneda_market_making.start as strategy_start
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.strategy.avellaneda_market_making.avellaneda_market_making_config_map import (
    avellaneda_market_making_config_map as strategy_cmap
)
from test.hummingbot.strategy import assign_config_default


class AvellanedaStartTest(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.strategy = None
        self.markets = {"binance": ExchangeBase()}
        self.notifications = []
        self.log_errors = []
        assign_config_default(strategy_cmap)
        strategy_cmap.get("exchange").value = "binance"
        strategy_cmap.get("market").value = "balancer"
        strategy_cmap.get("execution_timeframe").value = "from_date_to_date"
        strategy_cmap.get("start_time").value = "2021-11-18 15:00:00"
        strategy_cmap.get("end_time").value = "2021-11-18 16:00:00"
        strategy_cmap.get("order_amount").value = Decimal("1")
        strategy_cmap.get("order_refresh_time").value = 60.
        strategy_cmap.get("hanging_orders_enabled").value = True
        strategy_cmap.get("hanging_orders_cancel_pct").value = Decimal("1")
        # strategy_cmap.get("hanging_orders_aggregation_type").value = "VOLUME_WEIGHTED"
        strategy_cmap.get("min_spread").value = Decimal("2")
        strategy_cmap.get("risk_factor").value = Decimal("1.11")
        strategy_cmap.get("order_levels").value = Decimal("4")
        strategy_cmap.get("level_distances").value = Decimal("1")
        strategy_cmap.get("order_amount_shape_factor").value = Decimal("3.33")

        self.raise_exception_for_market_initialization = False

    def _initialize_market_assets(self, market, trading_pairs):
        return [("ETH", "USDT")]

    def _initialize_markets(self, market_names):
        if self.raise_exception_for_market_initialization:
            raise Exception("Exception for testing")

    def _notify(self, message):
        self.notifications.append(message)

    def logger(self):
        return self

    def error(self, message, exc_info):
        self.log_errors.append(message)

    @unittest.mock.patch('hummingbot.strategy.avellaneda_market_making.start.HummingbotApplication')
    def test_parameters_strategy_creation(self, mock_hbot):
        mock_hbot.main_application().strategy_file_name = "test.csv"
        strategy_start.start(self)
        self.assertEqual(self.strategy.execution_timeframe, "from_date_to_date")
        self.assertEqual(self.strategy.start_time, datetime.datetime(2021, 11, 18, 15, 0))
        self.assertEqual(self.strategy.end_time, datetime.datetime(2021, 11, 18, 16, 0))
        self.assertEqual(self.strategy.min_spread, Decimal("2"))
        self.assertEqual(self.strategy.gamma, Decimal("1.11"))
        self.assertEqual(self.strategy.eta, Decimal("3.33"))
        self.assertEqual(self.strategy.order_levels, Decimal("4"))
        self.assertEqual(self.strategy.level_distances, Decimal("1"))
        self.assertTrue(all(c is not None for c in (self.strategy.gamma, self.strategy.eta)))
        strategy_start.start(self)
        self.assertTrue(all(c is not None for c in (self.strategy.min_spread, self.strategy.gamma)))

    def test_strategy_creation_when_something_fails(self):
        self.raise_exception_for_market_initialization = True
        strategy_start.start(self)
        self.assertEqual(len(self.notifications), 1)
        self.assertEqual(self.notifications[0], "Exception for testing")
        self.assertEqual(len(self.log_errors), 1)
        self.assertEqual(self.log_errors[0], "Unknown error during initialization.")
