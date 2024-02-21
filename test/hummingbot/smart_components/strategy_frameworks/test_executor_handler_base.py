import random
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import MagicMock, patch

import pandas as pd

from hummingbot.core.data_type.common import OrderType, PositionAction, PositionSide
from hummingbot.logger import HummingbotLogger
from hummingbot.smart_components.strategy_frameworks.controller_base import ControllerBase
from hummingbot.smart_components.strategy_frameworks.executor_handler_base import ExecutorHandlerBase


class TestExecutorHandlerBase(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        super().setUp()
        self.mock_strategy = MagicMock()
        self.mock_controller = MagicMock(spec=ControllerBase)
        self.mock_controller.config = MagicMock()
        self.mock_controller.config.strategy_name = "test_strategy"
        self.mock_controller.config.order_levels = []
        self.mock_controller.get_csv_prefix = MagicMock(return_value="test_strategy")
        self.executor_handler = ExecutorHandlerBase(self.mock_strategy, self.mock_controller)

    def test_initialization(self):
        self.assertEqual(self.executor_handler.strategy, self.mock_strategy)
        self.assertEqual(self.executor_handler.controller, self.mock_controller)
        self.assertTrue(isinstance(self.executor_handler.logger(), HummingbotLogger))

    def test_terminate_control_loop(self):
        self.executor_handler.stop()
        self.assertTrue(self.executor_handler.terminated.is_set())

    def test_on_stop(self):
        self.executor_handler.on_stop()
        self.mock_controller.stop.assert_called_once()

    @patch("hummingbot.connector.markets_recorder.MarketsRecorder", new_callable=MagicMock)
    def test_store_executor_removes_executor(self, market_recorder_mock):
        market_recorder_mock.store_position_executor = MagicMock()
        mock_executor = MagicMock()
        mock_executor.to_json = MagicMock(return_value={"timestamp": 123445634,
                                                        "exchange": "binance_perpetual",
                                                        "trading_pair": "BTC-USDT",
                                                        "side": "BUY",
                                                        "amount": 100,
                                                        "trade_pnl": 0.1,
                                                        "trade_pnl_quote": 10,
                                                        "cum_fee_quote": 1,
                                                        "net_pnl_quote": 9,
                                                        "net_pnl": 0.09,
                                                        "close_timestamp": 1234156423,
                                                        "executor_status": "CLOSED",
                                                        "close_type": "TAKE_PROFIT",
                                                        "entry_price": 100,
                                                        "close_price": 110,
                                                        "sl": 0.03,
                                                        "tp": 0.05,
                                                        "tl": 0.1,
                                                        "open_order_type": "MARKET",
                                                        "take_profit_order_type": "MARKET",
                                                        "stop_loss_order_type": "MARKET",
                                                        "time_limit_order_type": "MARKET",
                                                        "leverage": 10,
                                                        })
        level_id = "BUY_1"
        self.executor_handler.position_executors[level_id] = mock_executor
        self.executor_handler.store_position_executor(level_id)
        self.assertIsNone(self.executor_handler.position_executors[level_id])

    @patch("hummingbot.smart_components.strategy_frameworks.executor_handler_base.PositionExecutor")
    def test_create_position_executor(self, mock_position_executor):
        mock_position_config = MagicMock()
        mock_order_level = MagicMock()
        self.executor_handler.create_position_executor(mock_position_config, mock_order_level)
        mock_position_executor.assert_called_once_with(self.mock_strategy, mock_position_config, update_interval=1.0)
        self.assertIsNotNone(self.executor_handler.position_executors[mock_order_level])

    def generate_random_data(self, num_rows):
        data = {
            "net_pnl": [random.uniform(-1, 1) for _ in range(num_rows)],
            "net_pnl_quote": [random.uniform(0, 1000) for _ in range(num_rows)],
            "amount": [random.uniform(0, 100) for _ in range(num_rows)],
            "side": [random.choice(["BUY", "SELL"]) for _ in range(num_rows)],
            "close_type": [random.choice(["type1", "type2", "type3"]) for _ in range(num_rows)],
            "timestamp": [pd.Timestamp.now() for _ in range(num_rows)]
        }
        return pd.DataFrame(data)

    def test_summarize_executors_df(self):
        df = self.generate_random_data(100)  # Generate a DataFrame with 100 rows of random data

        summary = ExecutorHandlerBase.summarize_executors_df(df)

        # Check if the summary values match the DataFrame's values
        self.assertEqual(summary["net_pnl"], df["net_pnl"].sum())
        self.assertEqual(summary["net_pnl_quote"], df["net_pnl_quote"].sum())
        self.assertEqual(summary["total_executors"], df.shape[0])
        self.assertEqual(summary["total_executors_with_position"], df[df["net_pnl"] != 0].shape[0])
        self.assertEqual(summary["total_volume"], df[df["net_pnl"] != 0]["amount"].sum() * 2)
        self.assertEqual(summary["total_long"], (df[df["net_pnl"] != 0]["side"] == "BUY").sum())
        self.assertEqual(summary["total_short"], (df[df["net_pnl"] != 0]["side"] == "SELL").sum())

    def test_close_open_positions(self):
        # Mocking the connector and its methods
        mock_connector = MagicMock()
        mock_connector.get_mid_price.return_value = 100  # Mocking the mid price to be 100

        # Mocking the account_positions of the connector
        mock_position1 = MagicMock(trading_pair="BTC-USD", position_side=PositionSide.LONG, amount=10)
        mock_position2 = MagicMock(trading_pair="BTC-USD", position_side=PositionSide.SHORT, amount=-10)
        mock_connector.account_positions = {
            "pos1": mock_position1,
            "pos2": mock_position2
        }

        # Setting the mock connector to the strategy's connectors
        self.mock_strategy.connectors = {"mock_connector": mock_connector}

        # Calling the method
        self.executor_handler.close_open_positions(connector_name="mock_connector", trading_pair="BTC-USD")

        # Asserting that the strategy's sell and buy methods were called with the expected arguments
        self.mock_strategy.sell.assert_called_once_with(
            connector_name="mock_connector",
            trading_pair="BTC-USD",
            amount=10,
            order_type=OrderType.MARKET,
            price=100,
            position_action=PositionAction.CLOSE
        )
        self.mock_strategy.buy.assert_called_once_with(
            connector_name="mock_connector",
            trading_pair="BTC-USD",
            amount=10,
            order_type=OrderType.MARKET,
            price=100,
            position_action=PositionAction.CLOSE
        )

    def test_get_active_executors_df(self):
        position_executor_mock = MagicMock()
        position_executor_mock.to_json = MagicMock(return_value={"entry_price": Decimal("100"),
                                                                 "amount": Decimal("10")})
        self.executor_handler.position_executors = {
            "level1": position_executor_mock,
            "level2": position_executor_mock,
            "level3": position_executor_mock
        }
        active_executors_df = self.executor_handler.get_active_executors_df()
        self.assertEqual(active_executors_df.shape[0], 3)
