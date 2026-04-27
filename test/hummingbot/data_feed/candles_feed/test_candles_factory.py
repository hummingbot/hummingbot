import unittest

from hummingbot.data_feed.candles_feed.binance_perpetual_candles import BinancePerpetualCandles
from hummingbot.data_feed.candles_feed.binance_spot_candles import BinanceSpotCandles
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.data_feed.candles_feed.hyperliquid_perpetual_candles.hyperliquid_perpetual_candles import (
    HyperliquidPerpetualCandles,
)
from hummingbot.data_feed.candles_feed.hyperliquid_spot_candles.hyperliquid_spot_candles import HyperliquidSpotCandles
from hummingbot.data_feed.candles_feed.lighter_perpetual_candles import LighterPerpetualCandles
from hummingbot.data_feed.candles_feed.lighter_spot_candles import LighterSpotCandles


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

    def test_get_lighter_candles_spot(self):
        candles = CandlesFactory.get_candle(CandlesConfig(
            connector="lighter",
            trading_pair="BTC-USDC",
            interval="1h"
        ))
        self.assertIsInstance(candles, LighterSpotCandles)
        candles.stop()

    def test_get_lighter_candles_perpetual(self):
        candles = CandlesFactory.get_candle(CandlesConfig(
            connector="lighter_perpetual",
            trading_pair="BTC-USDC",
            interval="1h"
        ))
        self.assertIsInstance(candles, LighterPerpetualCandles)
        candles.stop()

    def test_get_non_existing_candles(self):
        with self.assertRaises(Exception):
            CandlesFactory.get_candle(CandlesConfig(
                connector="hbot",
                trading_pair="BTC-USDT",
                interval="1m"
            ))

    def test_get_hyperliquid_candles_spot(self):
        candles = CandlesFactory.get_candle(CandlesConfig(
            connector="hyperliquid",
            trading_pair="ETH-USDC",
            interval="1m",
            max_records=50,
        ))
        self.assertIsInstance(candles, HyperliquidSpotCandles)
        candles.stop()

    def test_get_hyperliquid_candles_perpetual(self):
        candles = CandlesFactory.get_candle(CandlesConfig(
            connector="hyperliquid_perpetual",
            trading_pair="ETH-USDC",
            interval="3m",
            max_records=50,
        ))
        self.assertIsInstance(candles, HyperliquidPerpetualCandles)
        candles.stop()
