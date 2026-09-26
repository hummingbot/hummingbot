import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase

import numpy as np

from hummingbot.data_feed.candles_feed.binance_perpetual_candles import BinancePerpetualCandles


class TestCandlesBaseWsInterruption(IsolatedAsyncioWrapperTestCase):
    __test__ = True

    def setUp(self):
        super().setUp()
        self.trading_pair = "BTC-USDT"
        self.interval = "1h"

    async def test_on_order_stream_interruption_clears_ws_candle_available(self):
        feed = BinancePerpetualCandles(
            trading_pair=self.trading_pair, interval=self.interval, max_records=10
        )
        row = np.array([1000.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0], dtype=float)
        feed._candles.append(row)
        feed._ws_candle_available.set()
        await feed._on_order_stream_interruption(None)
        self.assertEqual(len(feed._candles), 0)
        self.assertFalse(feed._ws_candle_available.is_set())

    async def test_fill_historical_waits_when_ws_event_set_but_deque_empty(self):
        """If _candles was cleared without clearing the event, do not index _candles[0]."""
        feed = BinancePerpetualCandles(
            trading_pair=self.trading_pair, interval=self.interval, max_records=10
        )
        feed._ws_candle_available.set()
        self.assertEqual(len(feed._candles), 0)
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(feed.fill_historical_candles(), timeout=0.05)
