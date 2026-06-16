import unittest

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.data_feed.candles_feed.binance_perpetual_candles import BinancePerpetualCandles
from hummingbot.data_feed.candles_feed.binance_spot_candles import BinanceSpotCandles
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig


class TestCandlesFactory(unittest.TestCase):
    def test_get_binance_candles_spot(self):
        candles = CandlesFactory.get_candle(CandlesConfig(
            connector="binance",
            trading_pair="BTC-USDT",
            interval="1m"
        ))
        self.assertIsInstance(candles, BinanceSpotCandles)
        candles.stop()

    def test_get_binance_candles_perpetuals(self):
        candles = CandlesFactory.get_candle(CandlesConfig(
            connector="binance_perpetual",
            trading_pair="BTC-USDT",
            interval="1m"
        ))
        self.assertIsInstance(candles, BinancePerpetualCandles)
        candles.stop()

    def test_get_non_existing_candles(self):
        with self.assertRaises(Exception):
            CandlesFactory.get_candle(CandlesConfig(
                connector="hbot",
                trading_pair="BTC-USDT",
                interval="1m"
            ))

    def test_get_candle_without_throttler_creates_own(self):
        # Standalone behaviour: no throttler passed -> the feed builds its own AsyncThrottler.
        candles = CandlesFactory.get_candle(CandlesConfig(
            connector="binance",
            trading_pair="BTC-USDT",
            interval="1m"
        ))
        self.assertIsInstance(candles._api_factory._throttler, AsyncThrottler)
        candles.stop()

    def test_get_candle_with_shared_throttler_is_reused(self):
        # When a throttler is injected the feed reuses that exact instance (shared rate-limit budget)
        # and registers its own limit ids on it without overwriting the existing ones.
        shared_throttler = AsyncThrottler(rate_limits=[])
        candles = CandlesFactory.get_candle(
            CandlesConfig(connector="binance", trading_pair="BTC-USDT", interval="1m"),
            throttler=shared_throttler,
        )
        self.assertIsInstance(candles, BinanceSpotCandles)
        # Same throttler instance is used by the feed's request factory.
        self.assertIs(candles._api_factory._throttler, shared_throttler)
        # The feed's own limit ids are now registered on the shared throttler.
        for rate_limit in candles.rate_limits:
            self.assertIn(rate_limit.limit_id, shared_throttler._id_to_limit_map)
        candles.stop()
