import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from hummingbot.core.data_type.common import PriceType
from hummingbot.core.data_type.order_book_query_result import OrderBookQueryResult
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy.strategy_v2_base import MarketDataProvider


class TestMarketDataProvider(unittest.TestCase):
    def setUp(self):
        self.mock_connector = MagicMock()
        self.connectors = {"mock_connector": self.mock_connector}
        self.provider = MarketDataProvider(self.connectors)

    def test_initialize_candles_feed(self):
        with patch('hummingbot.data_feed.candles_feed.candles_factory.CandlesFactory.get_candle', return_value=MagicMock()):
            config = CandlesConfig(connector="mock_connector", trading_pair="BTC-USDT", interval="1m", max_records=100)
            self.provider.initialize_candles_feed(config)
            self.assertTrue("mock_connector_BTC-USDT_1m" in self.provider.candles_feeds)

    def test_stop(self):
        mock_candles_feed = MagicMock()
        self.provider.candles_feeds = {"mock_feed": mock_candles_feed}
        self.provider.stop()
        mock_candles_feed.stop.assert_called_once()
        self.assertEqual(len(self.provider.candles_feeds), 0)

    def test_get_order_book(self):
        self.mock_connector.get_order_book.return_value = "mock_order_book"
        result = self.provider.get_order_book("mock_connector", "BTC-USDT")
        self.assertEqual(result, "mock_order_book")

    def test_get_price_by_type(self):
        self.mock_connector.get_price_by_type.return_value = 10000
        price = self.provider.get_price_by_type("mock_connector", "BTC-USDT", PriceType.MidPrice)
        self.assertEqual(price, 10000)

    @patch.object(CandlesBase, "start", MagicMock())
    def test_get_candles_df(self):
        self.provider.initialize_candles_feed(
            CandlesConfig(connector="binance", trading_pair="BTC-USDT", interval="1m", max_records=100))
        result = self.provider.get_candles_df("binance", "BTC-USDT", "1m", 100)
        self.assertIsInstance(result, pd.DataFrame)

    def test_get_trading_pairs(self):
        self.mock_connector.trading_pairs = ["BTC-USDT"]
        trading_pairs = self.provider.get_trading_pairs("mock_connector")
        self.assertIn("BTC-USDT", trading_pairs)

    def test_get_price_for_volume(self):
        self.mock_connector.get_order_book.return_value = MagicMock(
            get_price_for_volume=MagicMock(return_value=OrderBookQueryResult(100, 2, 100, 2)))
        result = self.provider.get_price_for_volume("mock_connector", "BTC-USDT", 1, True)
        self.assertIsInstance(result, OrderBookQueryResult)

    def test_get_order_book_snapshot(self):
        mock_order_book = MagicMock()
        mock_order_book.snapshot = (pd.DataFrame(), pd.DataFrame())
        self.mock_connector.get_order_book.return_value = mock_order_book
        snapshot = self.provider.get_order_book_snapshot("mock_connector", "BTC-USDT")
        self.assertIsInstance(snapshot, tuple)
        self.assertIsInstance(snapshot[0], pd.DataFrame)
        self.assertIsInstance(snapshot[1], pd.DataFrame)

    def test_get_price_for_quote_volume(self):
        self.mock_connector.get_order_book.return_value = MagicMock(
            get_price_for_quote_volume=MagicMock(return_value=OrderBookQueryResult(100, 2, 100, 2)))
        result = self.provider.get_price_for_quote_volume("mock_connector", "BTC-USDT", 1, True)
        self.assertIsInstance(result, OrderBookQueryResult)

    def test_get_volume_for_price(self):
        self.mock_connector.get_order_book.return_value = MagicMock(
            get_volume_for_price=MagicMock(return_value=OrderBookQueryResult(100, 2, 100, 2)))
        result = self.provider.get_volume_for_price("mock_connector", "BTC-USDT", 100, True)
        self.assertIsInstance(result, OrderBookQueryResult)

    def test_get_quote_volume_for_price(self):
        self.mock_connector.get_order_book.return_value = MagicMock(
            get_quote_volume_for_price=MagicMock(return_value=OrderBookQueryResult(100, 2, 100, 2)))
        result = self.provider.get_quote_volume_for_price("mock_connector", "BTC-USDT", 100, True)
        self.assertIsInstance(result, OrderBookQueryResult)

    def test_get_vwap_for_volume(self):
        self.mock_connector.get_order_book.return_value = MagicMock(
            get_vwap_for_volume=MagicMock(return_value=OrderBookQueryResult(100, 2, 100, 2)))
        result = self.provider.get_vwap_for_volume("mock_connector", "BTC-USDT", 1, True)
        self.assertIsInstance(result, OrderBookQueryResult)

    def test_stop_candle_feed(self):
        # Mocking a candle feed
        mock_candles_feed = MagicMock()
        config = CandlesConfig(connector="mock_connector", trading_pair="BTC-USDT", interval="1m", max_records=100)
        key = "mock_connector_BTC-USDT_1m"
        self.provider.candles_feeds[key] = mock_candles_feed

        # Calling stop_candle_feed and asserting behavior
        self.provider.stop_candle_feed(config)
        mock_candles_feed.stop.assert_called_once()
        self.assertNotIn(key, self.provider.candles_feeds)

    def test_ready(self):
        # Mocking connector and candle feed readiness
        self.mock_connector.ready = True
        mock_candles_feed = MagicMock(ready=True)
        self.provider.candles_feeds = {"mock_feed": mock_candles_feed}

        # Checking if the provider is ready
        self.assertTrue(self.provider.ready)

        # Testing not ready scenarios
        self.mock_connector.ready = False
        self.assertFalse(self.provider.ready)

        self.mock_connector.ready = True
        mock_candles_feed.ready = False
        self.assertFalse(self.provider.ready)
