import unittest

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
