import unittest
from unittest.mock import MagicMock

import pandas as pd

from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.strategy_frameworks.market_making import (
    MarketMakingControllerBase,
    MarketMakingControllerConfigBase,
)


class TestMarketMakingControllerBase(unittest.TestCase):

    def setUp(self):
        # Mocking the CandlesConfig
        self.mock_candles_config = CandlesConfig(
            connector="binance",
            trading_pair="BTC-USDT",
            interval="1m"
        )

        # Mocking the MarketMakingControllerConfigBase
        self.mock_controller_config = MarketMakingControllerConfigBase(
            strategy_name="dman_strategy",
            exchange="binance",
            trading_pair="BTC-USDT",
            candles_config=[self.mock_candles_config],
            order_levels=[]
        )

        # Instantiating the MarketMakingControllerBase
        self.controller = MarketMakingControllerBase(
            config=self.mock_controller_config,
        )

    def test_get_price_and_spread_multiplier(self):
        mock_candles_df = pd.DataFrame({"price_multiplier": [1.0, 2.0, 3.0], "spread_multiplier": [0.1, 0.2, 0.3]})
        self.controller.get_processed_data = MagicMock(return_value=mock_candles_df)
        price_multiplier, spread_multiplier = self.controller.get_price_and_spread_multiplier()
        self.assertEqual(price_multiplier, 3.0)
        self.assertEqual(spread_multiplier, 0.3)

    def test_update_strategy_markets_dict(self):
        markets_dict = {}
        updated_markets_dict = self.controller.update_strategy_markets_dict(markets_dict)
        self.assertEqual(updated_markets_dict, {"binance": {"BTC-USDT"}})

    def test_is_perpetual_true(self):
        self.controller.config.exchange = "mock_exchange_perpetual"
        self.assertTrue(self.controller.is_perpetual)

    def test_is_perpetual_false(self):
        self.controller.config.exchange = "mock_regular_exchange"
        self.assertFalse(self.controller.is_perpetual)

    def test_refresh_order_condition(self):
        with self.assertRaises(NotImplementedError):
            self.controller.refresh_order_condition(None, None)

    def test_early_stop_condition(self):
        with self.assertRaises(NotImplementedError):
            self.controller.early_stop_condition(None, None)

    def test_cooldown_condition(self):
        with self.assertRaises(NotImplementedError):
            self.controller.cooldown_condition(None, None)

    def test_get_position_config(self):
        with self.assertRaises(NotImplementedError):
            self.controller.get_position_config(None)

    def test_get_candles_with_price_and_spread_multipliers(self):
        with self.assertRaises(NotImplementedError):
            self.controller.get_processed_data()
