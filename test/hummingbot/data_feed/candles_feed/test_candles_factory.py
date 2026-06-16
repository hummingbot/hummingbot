import importlib
import os
import unittest

import hummingbot.data_feed.candles_feed as candles_feed_pkg
from hummingbot.connector.exchange.binance import binance_constants
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.data_feed.candles_feed.binance_perpetual_candles import BinancePerpetualCandles
from hummingbot.data_feed.candles_feed.binance_spot_candles import (
    BinanceSpotCandles,
    constants as binance_spot_constants,
)
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

    def test_no_candle_feed_links_to_undefined_pool(self):
        # Regression guard for the phantom "raw" pool: every linked_limit a candle feed declares
        # must resolve to a limit_id defined in that same feed's RATE_LIMITS, otherwise the link is
        # silently dropped by get_related_limits and the endpoint is not throttled by that pool.
        base = os.path.dirname(candles_feed_pkg.__file__)
        unresolved = []
        for name in sorted(os.listdir(base)):
            constants_path = os.path.join(base, name, "constants.py")
            if not os.path.isfile(constants_path):
                continue
            module = importlib.import_module(f"hummingbot.data_feed.candles_feed.{name}.constants")
            rate_limits = getattr(module, "RATE_LIMITS", None)
            if not rate_limits:
                continue
            defined = {rl.limit_id for rl in rate_limits}
            for rl in rate_limits:
                for pair in rl.linked_limits or []:
                    if pair.limit_id not in defined:
                        unresolved.append(f"{name}: {rl.limit_id} -> {pair.limit_id}")
        self.assertEqual(unresolved, [], f"Candle feeds link to undefined pools: {unresolved}")

    def test_klines_consume_connector_pool_when_shared(self):
        # Coordination: when the feed shares the connector's throttler, its klines endpoint must
        # consume from the connector's existing pool (same RateLimit object -> single shared budget).
        connector_throttler = AsyncThrottler(rate_limits=list(binance_constants.RATE_LIMITS))
        connector_pool = connector_throttler._id_to_limit_map[binance_constants.REQUEST_WEIGHT]
        candles = CandlesFactory.get_candle(
            CandlesConfig(connector="binance", trading_pair="BTC-USDT", interval="1m"),
            throttler=connector_throttler,
        )
        _rate_limit, related = connector_throttler.get_related_limits(binance_spot_constants.CANDLES_ENDPOINT)
        # The klines endpoint links to the connector's REQUEST_WEIGHT pool, and it is the very same
        # object the connector owns (add_rate_limits skips the colliding pool id, keeping the connector's).
        self.assertTrue(any(pool is connector_pool for pool, _weight in related))
        candles.stop()
