import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd

from hummingbot.core.data_type.common import TradeType
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.executors.position_executor.data_types import TripleBarrierConf
from hummingbot.smart_components.order_level_distributions.order_level_builder import OrderLevel
from hummingbot.smart_components.strategy_frameworks.directional_trading import (
    DirectionalTradingControllerBase,
    DirectionalTradingControllerConfigBase,
)


class TestDirectionalTradingControllerBase(unittest.TestCase):

    def setUp(self):
        self.mock_candles_config = CandlesConfig(
            connector="binance",
            trading_pair="BTC-USDT",
            interval="1m"
        )
        # Mocking the DirectionalTradingControllerConfigBase
        self.mock_controller_config = DirectionalTradingControllerConfigBase(
            strategy_name="directional_strategy",
            exchange="binance",
            trading_pair="BTC-USDT",
            candles_config=[self.mock_candles_config],
            order_levels=[],
        )

        # Instantiating the DirectionalTradingControllerBase
        self.controller = DirectionalTradingControllerBase(
            config=self.mock_controller_config,
        )

    def test_filter_executors_df(self):
        mock_df = pd.DataFrame({"trading_pair": ["BTC-USDT", "ETH-USDT"]})
        self.controller.filter_executors_df = MagicMock(return_value=mock_df[mock_df["trading_pair"] == "BTC-USDT"])
        filtered_df = self.controller.filter_executors_df(mock_df)
        self.assertEqual(len(filtered_df), 1)

    def test_update_strategy_markets_dict(self):
        markets_dict = {}
        updated_markets_dict = self.controller.update_strategy_markets_dict(markets_dict)
        self.assertEqual(updated_markets_dict, {"binance": {"BTC-USDT"}})

    def test_is_perpetual(self):
        self.controller.config.exchange = "binance_perpetual"
        self.assertTrue(self.controller.is_perpetual)

    def test_get_signal(self):
        mock_df = pd.DataFrame({"signal": [1, -1, 1]})
        self.controller.get_processed_data = MagicMock(return_value=mock_df)
        signal = self.controller.get_signal()
        self.assertEqual(signal, 1)

    def test_early_stop_condition(self):
        with self.assertRaises(NotImplementedError):
            self.controller.early_stop_condition(None, None)

    def test_cooldown_condition(self):
        with self.assertRaises(NotImplementedError):
            self.controller.cooldown_condition(None, None)

    def test_get_processed_data(self):
        with self.assertRaises(NotImplementedError):
            self.controller.get_processed_data()

    @patch(
        "hummingbot.smart_components.strategy_frameworks.directional_trading.directional_trading_controller_base.format_df_for_printout")
    def test_to_format_status(self, mock_format_df_for_printout):
        # Create a mock DataFrame
        mock_df = pd.DataFrame({
            "timestamp": ["2021-01-01", "2021-01-02", "2021-01-03", "2021-01-04"],
            "open": [1, 2, 3, 4],
            "low": [1, 2, 3, 4],
            "high": [1, 2, 3, 4],
            "close": [1, 2, 3, 4],
            "volume": [1, 2, 3, 4],
            "signal": [1, -1, 1, -1]
        })

        # Mock the get_processed_data method to return the mock DataFrame
        self.controller.get_processed_data = MagicMock(return_value=mock_df)

        # Mock the format_df_for_printout function to return a sample formatted string
        mock_format_df_for_printout.return_value = "formatted_string"

        # Call the method and get the result
        result = self.controller.to_format_status()

        # Check if the result contains the expected formatted string
        self.assertIn("formatted_string", result)

    @patch("hummingbot.smart_components.strategy_frameworks.controller_base.ControllerBase.get_close_price")
    def test_get_position_config(self, mock_get_closest_price):
        order_level = OrderLevel(
            level=1, side=TradeType.BUY, order_amount_usd=Decimal("10"),
            triple_barrier_conf=TripleBarrierConf(
                stop_loss=Decimal("0.03"), take_profit=Decimal("0.02"),
                time_limit=60 * 2,
            ))
        mock_get_closest_price.return_value = Decimal("100")
        # Create a mock DataFrame
        mock_df = pd.DataFrame({
            "timestamp": ["2021-01-01", "2021-01-02", "2021-01-03", "2021-01-04"],
            "open": [1, 2, 3, 4],
            "low": [1, 2, 3, 4],
            "high": [1, 2, 3, 4],
            "close": [1, 2, 3, 4],
            "volume": [1, 2, 3, 4],
            "signal": [1, -1, 1, -1]
        })

        # Mock the get_processed_data method to return the mock DataFrame
        self.controller.get_processed_data = MagicMock(return_value=mock_df)
        position_config = self.controller.get_position_config(order_level, 1)
        self.assertEqual(position_config.trading_pair, "BTC-USDT")
        self.assertEqual(position_config.exchange, "binance")
        self.assertEqual(position_config.side, TradeType.BUY)
        self.assertEqual(position_config.amount, Decimal("0.1"))
        self.assertEqual(position_config.entry_price, Decimal("100"))
