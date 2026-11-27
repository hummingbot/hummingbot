import unittest

from pydantic import SecretStr

from hummingbot.data_feed.liquidations_feed.agentfeed import AgentFeedLiquidations
from hummingbot.data_feed.liquidations_feed.binance import BinancePerpetualLiquidations
from hummingbot.data_feed.liquidations_feed.liquidations_factory import (
    LiquidationsConfig,
    LiquidationsFactory,
    UnsupportedConnectorException,
)


class TestLiquidationsFactory(unittest.TestCase):

    def test_get_binance_liquidations(self):
        candles = LiquidationsFactory.get_liquidations_feed(LiquidationsConfig(
            connector="binance"
        ))
        self.assertIsInstance(candles, BinancePerpetualLiquidations)
        candles.stop()

    def test_get_unknown_liquidations_feed(self):
        with self.assertRaises(UnsupportedConnectorException):
            LiquidationsFactory.get_liquidations_feed(LiquidationsConfig(
                connector="unknown"
            ))

    def test_get_agentfeed_liquidations(self):
        feed = LiquidationsFactory.get_liquidations_feed(LiquidationsConfig(
            connector="agentfeed",
            trading_pairs={"BTC-USDT"},
            api_key=SecretStr("afk_FactoryKey"),
            poll_interval_seconds=45,
        ))
        self.assertIsInstance(feed, AgentFeedLiquidations)
        self.assertEqual("afk_FactoryKey", feed._api_key)
        self.assertEqual(45, feed._poll_interval)
        self.assertNotIn("afk_FactoryKey", repr(LiquidationsConfig(connector="agentfeed", api_key=SecretStr("afk_FactoryKey"))))
        feed.stop()

    def test_a_source_that_needs_nothing_extra_is_built_as_before(self):
        feed = LiquidationsFactory.get_liquidations_feed(LiquidationsConfig(
            connector="binance",
            api_key=SecretStr("afk_NotForBinance"),
        ))
        self.assertIsInstance(feed, BinancePerpetualLiquidations)
        feed.stop()
