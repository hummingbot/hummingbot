import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pandas as pd

from controllers.directional_trading.bollinger_v1 import BollingerV1Controller, BollingerV1ControllerConfig
from controllers.directional_trading.bollingrid import BollinGridController, BollinGridControllerConfig
from controllers.directional_trading.macd_bb_v1 import MACDBBV1Controller, MACDBBV1ControllerConfig
from controllers.directional_trading.supertrend_v1 import SuperTrend, SuperTrendConfig
from controllers.market_making.pmm_dynamic import PMMDynamicController, PMMDynamicControllerConfig
from hummingbot.data_feed.market_data_provider import MarketDataProvider


def make_candles(n: int = 300) -> pd.DataFrame:
    i = np.arange(n, dtype=float)
    close = 100 + 5 * np.sin(i / 10) + 0.01 * i
    return pd.DataFrame({
        "timestamp": 1_700_000_000 + 60 * i,
        "open": np.r_[close[0], close[:-1]],
        "high": close + 0.5,
        "low": close - 0.5,
        "close": close,
        "volume": np.full(n, 10.0),
    })


def expected_bbp(close: pd.Series, length: int, std: float) -> pd.Series:
    mid = close.rolling(length).mean()
    dev = close.rolling(length).std(ddof=0)
    lower, upper = mid - std * dev, mid + std * dev
    return (close - lower) / (upper - lower)


class TestIndicatorControllers(IsolatedAsyncioWrapperTestCase):
    """The indicator controllers compute their signals from fin-primitives' pandas-ta compatible columns."""

    def setUp(self):
        self.candles = make_candles()
        self.market_data_provider = MagicMock(spec=MarketDataProvider)
        self.market_data_provider.get_candles_df = MagicMock(
            side_effect=lambda *args, **kwargs: self.candles.tail(kwargs.get("max_records", len(self.candles))).copy())
        self.actions_queue = AsyncMock(spec=asyncio.Queue)

    def make(self, controller_cls, config):
        return controller_cls(config=config, market_data_provider=self.market_data_provider,
                              actions_queue=self.actions_queue)

    async def test_bollinger_v1_signal_uses_bbp(self):
        config = BollingerV1ControllerConfig(id="bb", connector_name="binance_perpetual", trading_pair="ETH-USDT",
                                             bb_length=20, bb_std=2.0, bb_long_threshold=0.2, bb_short_threshold=0.8)
        controller = self.make(BollingerV1Controller, config)
        await controller.update_processed_data()
        features = controller.processed_data["features"]
        bbp = expected_bbp(features["close"], 20, 2.0)
        np.testing.assert_allclose(features["BBP_20_2.0"].iloc[-1], bbp.iloc[-1], rtol=1e-9)
        self.assertIn(controller.processed_data["signal"], (-1, 0, 1))

    async def test_bollingrid_reads_its_bbands_columns_and_honours_bb_std(self):
        # With pandas-ta 0.4 this controller raised KeyError: it reads BBP_{length}_{std}, while
        # pandas-ta 0.4 names the column BBP_{length}_{lower_std}_{upper_std} and ignores `std`.
        config = BollinGridControllerConfig(id="grid", connector_name="binance", trading_pair="ETH-USDT",
                                            bb_length=50, bb_std=1.5)
        controller = self.make(BollinGridController, config)
        await controller.update_processed_data()
        features = controller.processed_data["features"]
        bbp = expected_bbp(features["close"], 50, 1.5)
        np.testing.assert_allclose(features["BBP_50_1.5"].iloc[-1], bbp.iloc[-1], rtol=1e-9)
        self.assertTrue(np.isfinite(features["BBB_50_1.5"].iloc[-1]))
        self.assertIn(controller.processed_data["signal"], (-1, 0, 1))
        self.assertIn("grid_params", controller.processed_data)

    async def test_macd_bb_v1_computes_signal(self):
        config = MACDBBV1ControllerConfig(id="macd", connector_name="binance_perpetual", trading_pair="ETH-USDT",
                                          bb_length=20, macd_fast=12, macd_slow=26, macd_signal=9)
        controller = self.make(MACDBBV1Controller, config)
        await controller.update_processed_data()
        features = controller.processed_data["features"]
        self.assertTrue(np.isfinite(features["MACDh_12_26_9"].iloc[-1]))
        self.assertIn(controller.processed_data["signal"], (-1, 0, 1))

    async def test_supertrend_v1_direction_column(self):
        config = SuperTrendConfig(id="st", connector_name="binance_perpetual", trading_pair="ETH-USDT",
                                  length=20, multiplier=4.0, percentage_threshold=0.01)
        controller = self.make(SuperTrend, config)
        await controller.update_processed_data()
        direction = controller.processed_data["features"]["SUPERTd_20_4.0"].dropna()
        self.assertTrue(set(direction.unique()) <= {-1.0, 1.0})
        self.assertIn(controller.processed_data["signal"], (-1, 0, 1))

    async def test_pmm_dynamic_reference_price_and_spread(self):
        config = PMMDynamicControllerConfig(id="pmm", connector_name="binance", trading_pair="ETH-USDT")
        controller = self.make(PMMDynamicController, config)
        await controller.update_processed_data()
        self.assertGreater(controller.processed_data["reference_price"], Decimal("0"))
        self.assertGreater(controller.processed_data["spread_multiplier"], Decimal("0"))
