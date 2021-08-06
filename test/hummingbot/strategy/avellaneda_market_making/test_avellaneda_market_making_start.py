from decimal import Decimal
import unittest.mock
import hummingbot.strategy.avellaneda_market_making.start as strategy_start
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.strategy.avellaneda_market_making.avellaneda_market_making_config_map import (
    avellaneda_market_making_config_map as strategy_cmap
)
# from hummingbot.strategy.hanging_orders_tracker import HangingOrdersAggregationType
from test.hummingbot.strategy import assign_config_default


class AvellanedaStartTest(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.strategy = None
        self.markets = {"binance": ExchangeBase()}
        self.assets = set()
        self.notifications = []
        self.log_errors = []
        assign_config_default(strategy_cmap)
        strategy_cmap.get("exchange").value = "binance"
        strategy_cmap.get("market").value = "balancer"
        strategy_cmap.get("order_amount").value = Decimal("1")
        strategy_cmap.get("order_refresh_time").value = 60.
        strategy_cmap.get("hanging_orders_enabled").value = True
        strategy_cmap.get("hanging_orders_cancel_pct").value = Decimal("1")
        # strategy_cmap.get("hanging_orders_aggregation_type").value = "VOLUME_WEIGHTED"
        strategy_cmap.get("parameters_based_on_spread").value = True
        strategy_cmap.get("min_spread").value = Decimal("2")
        strategy_cmap.get("max_spread").value = Decimal("3")
        strategy_cmap.get("vol_to_spread_multiplier").value = Decimal("1.1")
        strategy_cmap.get("volatility_sensibility").value = Decimal("2.2")
        strategy_cmap.get("inventory_risk_aversion").value = Decimal("0.1")
        strategy_cmap.get("risk_factor").value = Decimal("1.11")
        strategy_cmap.get("order_book_depth_factor").value = Decimal("2.22")
        strategy_cmap.get("order_amount_shape_factor").value = Decimal("3.33")

        self.raise_exception_for_market_initialization = False

    def _initialize_market_assets(self, market, trading_pairs):
        return [("ETH", "USDT")]

    def _initialize_wallet(self, token_trading_pairs):
        pass

    def _initialize_markets(self, market_names):
        if self.raise_exception_for_market_initialization:
            raise Exception("Exception for testing")

    def _notify(self, message):
        self.notifications.append(message)

    def logger(self):
        return self

    def error(self, message, exc_info):
        self.log_errors.append(message)

    # @unittest.mock.patch('hummingbot.strategy.avellaneda_market_making.start.HummingbotApplication')
    # def test_hanging_orders_strategy_creation(self, mock_fname):
    #     mock_fname.main_application().strategy_file_name = "test.csv"
    #     strategy_start.start(self)
    #     self.assertEqual(self.strategy.order_amount, Decimal("1"))
    #     self.assertEqual(self.strategy.order_refresh_time, 60.)
    #     self.assertEqual(self.strategy.hanging_orders_tracker.aggregation_method,
    #                      HangingOrdersAggregationType.VOLUME_WEIGHTED)
    #     self.assertEqual(self.strategy.hanging_orders_tracker._hanging_orders_cancel_pct,
    #                      Decimal("0.01"))
    #     strategy_cmap.get("hanging_orders_enabled").value = False
    #     strategy_start.start(self)
    #     self.assertEqual(self.strategy.hanging_orders_tracker.aggregation_method,
    #                      HangingOrdersAggregationType.NO_AGGREGATION)

    @unittest.mock.patch('hummingbot.strategy.avellaneda_market_making.start.HummingbotApplication')
    def test_parameters_based_on_spread_strategy_creation(self, mock_hbot):
        mock_hbot.main_application().strategy_file_name = "test.csv"
        strategy_start.start(self)
        self.assertEqual(self.strategy.min_spread, Decimal("0.02"))
        self.assertEqual(self.strategy.max_spread, Decimal("0.03"))
        self.assertEqual(self.strategy.vol_to_spread_multiplier, Decimal("1.1"))
        self.assertEqual(self.strategy.volatility_sensibility, Decimal("0.022"))
        self.assertEqual(self.strategy.inventory_risk_aversion, Decimal("0.1"))
        self.assertTrue(all(c is None for c in (self.strategy.gamma, self.strategy.kappa, self.strategy.eta)))
        strategy_cmap.get("parameters_based_on_spread").value = False
        strategy_start.start(self)
        self.assertTrue(all(c is None for c in (self.strategy.min_spread, self.strategy.max_spread,
                                                self.strategy.vol_to_spread_multiplier,
                                                self.strategy.inventory_risk_aversion,
                                                self.strategy.volatility_sensibility)))
        self.assertEqual(self.strategy.gamma, Decimal("1.11"))
        self.assertEqual(self.strategy.kappa, Decimal("2.22"))
        self.assertEqual(self.strategy.eta, Decimal("3.33"))

    def test_strategy_creation_when_something_fails(self):
        self.raise_exception_for_market_initialization = True
        strategy_start.start(self)
        self.assertEqual(len(self.notifications), 1)
        self.assertEqual(self.notifications[0], "Exception for testing")
        self.assertEqual(len(self.log_errors), 1)
        self.assertEqual(self.log_errors[0], "Unknown error during initialization.")
