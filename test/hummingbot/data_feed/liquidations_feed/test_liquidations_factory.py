import unittest

from hummingbot.data_feed.liquidations_feed.binance import BinancePerpetualLiquidations
from hummingbot.data_feed.liquidations_feed.liquidations_factory import LiquidationsConfig, LiquidationsFactory


class TestCandlesFactory(unittest.TestCase):
    def test_get_binance_liquidations(self):
        candles = LiquidationsFactory.get_liquidations_feed(LiquidationsConfig(
            connector="binance"
        ))
        self.assertIsInstance(candles, BinancePerpetualLiquidations)
        candles.stop()
