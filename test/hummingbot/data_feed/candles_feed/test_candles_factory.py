import unittest

from hummingbot.data_feed.candles_feed.binance_perpetual_candles import BinancePerpetualCandles
from hummingbot.data_feed.candles_feed.binance_spot_candles import BinanceSpotCandles
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory


class TestCandlesFactory(unittest.TestCase):
    def test_get_binance_candles_spot(self):
        candles = CandlesFactory.get_candle(connector="binance", trading_pair="ETH-USDT")
        self.assertIsInstance(candles, BinanceSpotCandles)
        candles.stop()

    def test_get_binance_candles_perpetuals(self):
        candles = CandlesFactory.get_candle(connector="binance_perpetual", trading_pair="ETH-USDT")
        self.assertIsInstance(candles, BinancePerpetualCandles)
        candles.stop()

    def test_get_non_existing_candles(self):
        with self.assertRaises(Exception):
            CandlesFactory.get_candle(connector="hbot", trading_pair="ETH-USDT")
