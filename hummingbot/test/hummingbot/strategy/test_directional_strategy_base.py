import unittest
from unittest.mock import MagicMock, PropertyMock, patch

import pandas as pd

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from hummingbot.connector.test_support.mock_paper_exchange import MockPaperExchange
from hummingbot.core.clock import Clock
from hummingbot.core.clock_mode import ClockMode
from hummingbot.strategy.directional_strategy_base import DirectionalStrategyBase


class DirectionalStrategyBaseTest(unittest.TestCase):
    level = 0

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage().startswith(message)
                   for record in self.log_records)

    def setUp(self):
        self.log_records = []
        self.start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
        self.end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
        self.start_timestamp: float = self.start.timestamp()
        self.end_timestamp: float = self.end.timestamp()
        self.connector_name: str = "mock_paper_exchange"
        self.trading_pair: str = "HBOT-USDT"
        self.base_asset, self.quote_asset = self.trading_pair.split("-")
        self.base_balance: int = 500
        self.quote_balance: int = 5000
        self.initial_mid_price: int = 100
        self.clock_tick_size = 1
        self.clock: Clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)
        self.connector: MockPaperExchange = MockPaperExchange(
            client_config_map=ClientConfigAdapter(ClientConfigMap())
        )
        self.connector.set_balanced_order_book(trading_pair=self.trading_pair,
                                               mid_price=100,
                                               min_price=50,
                                               max_price=150,
                                               price_step_size=1,
                                               volume_step_size=10)
        self.connector.set_balance(self.base_asset, self.base_balance)
        self.connector.set_balance(self.quote_asset, self.quote_balance)
        self.connector.set_quantization_param(
            QuantizationParams(
                self.trading_pair, 6, 6, 6, 6
            )
        )
        self.clock.add_iterator(self.connector)
        DirectionalStrategyBase.markets = {self.connector_name: {self.trading_pair}}
        DirectionalStrategyBase.candles = []
        DirectionalStrategyBase.exchange = self.connector_name
        DirectionalStrategyBase.trading_pair = self.trading_pair
        self.strategy = DirectionalStrategyBase({self.connector_name: self.connector})
        self.strategy.logger().setLevel(1)
        self.strategy.logger().addHandler(self)

    def test_start(self):
        self.assertFalse(self.strategy.ready_to_trade)
        self.strategy.start(Clock(ClockMode.BACKTEST), self.start_timestamp)
        self.strategy.tick(self.start_timestamp + 10)
        self.assertTrue(self.strategy.ready_to_trade)

    def test_all_candles_ready(self):
        self.assertTrue(self.strategy.all_candles_ready)

    def test_is_perpetual(self):
        self.assertFalse(self.strategy.is_perpetual)

    def test_candles_formatted_list(self):
        columns = ["timestamp", "open", "low", "high", "close", "volume"]
        candles_df = pd.DataFrame(columns=columns,
                                  data=[[self.start_timestamp, 1, 2, 3, 4, 5],
                                        [self.start_timestamp + 1, 2, 3, 4, 5, 6]])
        candles_status = self.strategy.candles_formatted_list(candles_df, columns)
        self.assertTrue("timestamp" in candles_status[0])

    def test_get_active_executors(self):
        self.assertEqual(0, len(self.strategy.get_active_executors()))

    def test_format_status_not_started(self):
        self.assertEqual("Market connectors are not ready.", self.strategy.format_status())

    @patch("hummingbot.strategy.directional_strategy_base.DirectionalStrategyBase.get_signal")
    def test_format_status(self, signal_mock):
        signal_mock.return_value = 0
        self.clock.add_iterator(self.strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        position_executor_mock = MagicMock()
        position_executor_mock.to_format_status = MagicMock(return_value=["mock_position_executor"])
        self.strategy.stored_executors.append(position_executor_mock)
        self.strategy.active_executors.append(position_executor_mock)
        self.assertTrue("mock_position_executor" in self.strategy.format_status())

    @patch("hummingbot.strategy.directional_strategy_base.DirectionalStrategyBase.get_signal", new_callable=MagicMock)
    def test_get_position_config_signal_zero(self, signal):
        signal.return_value = 0
        self.assertIsNone(self.strategy.get_position_config())

    @patch("hummingbot.strategy.directional_strategy_base.DirectionalStrategyBase.get_signal", new_callable=MagicMock)
    def test_get_position_config_signal_positive(self, signal):
        signal.return_value = 1
        self.assertIsNotNone(self.strategy.get_position_config())

    def test_time_between_signals_condition(self):
        self.strategy.cooldown_after_execution = 10
        stored_executor_mock = MagicMock()
        stored_executor_mock.close_timestamp = self.start_timestamp
        self.strategy.stored_executors = [stored_executor_mock]
        # First scenario waiting for delay
        type(self.strategy).current_timestamp = PropertyMock(return_value=self.start_timestamp + 5)
        self.assertFalse(self.strategy.time_between_signals_condition)

        # Second scenario delay passed
        type(self.strategy).current_timestamp = PropertyMock(return_value=self.start_timestamp + 15)
        self.assertTrue(self.strategy.time_between_signals_condition)

        # Third scenario no stored executors
        self.strategy.stored_executors = []
        self.assertTrue(self.strategy.time_between_signals_condition)

    def test_max_active_executors_condition(self):
        self.strategy.max_executors = 1
        active_executor_mock = MagicMock()
        active_executor_mock.is_closed = False
        self.strategy.active_executors = [active_executor_mock]
        self.assertFalse(self.strategy.max_active_executors_condition)
        self.strategy.active_executors = []
        self.assertTrue(self.strategy.max_active_executors_condition)
