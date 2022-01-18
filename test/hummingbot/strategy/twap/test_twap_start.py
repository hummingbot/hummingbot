import unittest.mock
from decimal import Decimal

import hummingbot.strategy.twap.start as twap_start_module
import hummingbot.strategy.twap.twap_config_map as twap_config_map_module


class TwapStartTest(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()

        self.strategy = None
        self.markets = {"binance": None}
        self.notifications = []
        self.log_errors = []

        twap_config_map_module.twap_config_map.get("strategy").value = "twap"
        twap_config_map_module.twap_config_map.get("connector").value = "binance"
        twap_config_map_module.twap_config_map.get("order_step_size").value = Decimal(1)
        twap_config_map_module.twap_config_map.get("trade_side").value = "buy"
        twap_config_map_module.twap_config_map.get("target_asset_amount").value = Decimal(10)
        twap_config_map_module.twap_config_map.get("order_delay_time").value = 10
        twap_config_map_module.twap_config_map.get("trading_pair").value = "ETH-USDT"
        twap_config_map_module.twap_config_map.get("order_price").value = Decimal(2500)
        twap_config_map_module.twap_config_map.get("cancel_order_wait_time").value = 60
        twap_config_map_module.twap_config_map.get("is_time_span_execution").value = False
        twap_config_map_module.twap_config_map.get("is_delayed_start_execution").value = False

        self.raise_exception_for_market_initialization = False
        self.raise_exception_for_market_assets_initialization = False

    def _initialize_market_assets(self, market, trading_pairs):
        if self.raise_exception_for_market_assets_initialization:
            raise ValueError("ValueError for testing")
        return [trading_pair.split('-') for trading_pair in trading_pairs]

    def _initialize_markets(self, market_names):
        if self.raise_exception_for_market_initialization:
            raise Exception("Exception for testing")

    def _notify(self, message):
        self.notifications.append(message)

    def logger(self):
        return self

    def error(self, message, exc_info):
        self.log_errors.append(message)

    @unittest.mock.patch('hummingbot.strategy.twap.twap.TwapTradeStrategy.add_markets')
    def test_twap_strategy_creation(self, add_markets_mock):
        twap_start_module.start(self)

        self.assertTrue(self.strategy._is_buy)
        self.assertEqual(self.strategy._target_asset_amount, Decimal(10))
        self.assertEqual(self.strategy._order_step_size, Decimal(1))
        self.assertEqual(self.strategy._order_price, Decimal(2500))
        self.assertEqual(self.strategy._order_delay_time, 10)
        self.assertEqual(self.strategy._cancel_order_wait_time, Decimal(60))

    @unittest.mock.patch('hummingbot.strategy.twap.twap.TwapTradeStrategy.add_markets')
    def test_twap_strategy_creation_with_time_span_execution(self, add_markets_mock):
        twap_config_map_module.twap_config_map.get("is_time_span_execution").value = True
        twap_config_map_module.twap_config_map.get("start_datetime").value = "2021-06-23 10:00:00"
        twap_config_map_module.twap_config_map.get("end_datetime").value = "2021-06-23 11:00:00"
        twap_config_map_module.twap_config_map.get("order_delay_time").value = 360

        twap_start_module.start(self)

        self.assertTrue(self.strategy._is_buy)
        self.assertEqual(self.strategy._target_asset_amount, Decimal(10))
        self.assertEqual(self.strategy._order_step_size, Decimal(1))
        self.assertEqual(self.strategy._order_price, Decimal(2500))
        self.assertEqual(self.strategy._order_delay_time, 360)
        self.assertEqual(self.strategy._cancel_order_wait_time, Decimal(60))

    @unittest.mock.patch('hummingbot.strategy.twap.twap.TwapTradeStrategy.add_markets')
    def test_twap_strategy_creation_with_delayed_start_execution(self, add_markets_mock):
        twap_config_map_module.twap_config_map.get("is_delayed_start_execution").value = True
        twap_config_map_module.twap_config_map.get("start_datetime").value = "2021-06-23 10:00:00"

        twap_start_module.start(self)

        self.assertTrue(self.strategy._is_buy)
        self.assertEqual(self.strategy._target_asset_amount, Decimal(10))
        self.assertEqual(self.strategy._order_step_size, Decimal(1))
        self.assertEqual(self.strategy._order_price, Decimal(2500))
        self.assertEqual(self.strategy._order_delay_time, 10)
        self.assertEqual(self.strategy._cancel_order_wait_time, Decimal(60))

    def test_twap_strategy_creation_when_market_assets_initialization_fails(self):
        self.raise_exception_for_market_assets_initialization = True

        twap_start_module.start(self)

        self.assertEqual(len(self.notifications), 1)
        self.assertEqual(self.notifications[0], "ValueError for testing")

    def test_twap_strategy_creation_when_something_fails(self):
        self.raise_exception_for_market_initialization = True

        twap_start_module.start(self)

        self.assertEqual(len(self.notifications), 1)
        self.assertEqual(self.notifications[0], "Exception for testing")
        self.assertEqual(len(self.log_errors), 1)
        self.assertEqual(self.log_errors[0], "Unknown error during initialization.")
