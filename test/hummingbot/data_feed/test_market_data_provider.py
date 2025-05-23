from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd

from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import PriceType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book_query_result import OrderBookQueryResult
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy.strategy_v2_base import MarketDataProvider
from hummingbot.strategy_v2.executors.data_types import ConnectorPair


class TestMarketDataProvider(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        self.mock_connector = MagicMock()
        self.mock_connector.trading_rules = {"BTC-USDT": TradingRule("BTC-USDT", 0.01, 0.01, 0.01, 0.01, 0.01, 0.01)}
        self.connectors = {"mock_connector": self.mock_connector}
        self.provider = MarketDataProvider(self.connectors)

    def test_initialize_candles_feed(self):
        with patch('hummingbot.data_feed.candles_feed.candles_factory.CandlesFactory.get_candle', return_value=MagicMock()):
            config = CandlesConfig(connector="mock_connector", trading_pair="BTC-USDT", interval="1m", max_records=100)
            self.provider.initialize_candles_feed(config)
            self.assertTrue("mock_connector_BTC-USDT_1m" in self.provider.candles_feeds)

    def test_initialize_candles_feed_list(self):
        with patch('hummingbot.data_feed.candles_feed.candles_factory.CandlesFactory.get_candle', return_value=MagicMock()):
            config = [CandlesConfig(connector="mock_connector", trading_pair="BTC-USDT", interval="1m", max_records=100)]
            self.provider.initialize_candles_feed_list(config)
            self.assertTrue("mock_connector_BTC-USDT_1m" in self.provider.candles_feeds)

    def test_get_non_trading_connector(self):
        connector = self.provider.get_non_trading_connector("binance")
        self.assertEqual(connector._trading_required, False)
        with self.assertRaises(ValueError):
            self.provider.get_non_trading_connector("binance_invalid")

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

    def test_get_balance(self):
        self.mock_connector.get_balance.return_value = 100
        result = self.provider.get_balance("mock_connector", "BTC")
        self.assertEqual(result, 100)

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

    def test_get_trading_rules(self):
        result = self.provider.get_trading_rules("mock_connector", "BTC-USDT")
        self.assertEqual(result.min_notional_size, 0.01)

    def test_quantize_order_price(self):
        self.mock_connector.quantize_order_price.return_value = 100
        result = self.provider.quantize_order_price("mock_connector", "BTC-USDT", Decimal(100.0001))
        self.assertEqual(result, 100)

    def test_quantize_order_amount(self):
        self.mock_connector.quantize_order_amount.return_value = 100
        result = self.provider.quantize_order_amount("mock_connector", "BTC-USDT", Decimal(100.0001))
        self.assertEqual(result, 100)

    def test_get_rate(self):
        with patch("hummingbot.core.rate_oracle.rate_oracle.RateOracle.get_instance") as mock_get_instance:
            mock_get_instance.return_value.get_pair_rate.return_value = 100
            result = self.provider.get_rate("BTC-USDT")
            self.assertEqual(result, 100)

    def test_get_funding_info(self):
        self.mock_connector.get_funding_info.return_value = FundingInfo(
            trading_pair="BTC-USDT",
            index_price=Decimal("10000"),
            mark_price=Decimal("10000"),
            next_funding_utc_timestamp=1234567890,
            rate=Decimal("0.01")
        )
        result = self.provider.get_funding_info("mock_connector", "BTC-USDT")
        self.assertIsInstance(result, FundingInfo)
        self.assertEqual(result.trading_pair, "BTC-USDT")

    @patch.object(MarketDataProvider, "update_rates_task", MagicMock())
    def test_initialize_rate_sources(self):
        self.provider.initialize_rate_sources([ConnectorPair(connector_name="binance", trading_pair="BTC-USDT")])
        self.assertEqual(len(self.provider._rates_required), 1)
        self.provider.stop()

    async def test_safe_get_last_traded_prices(self):
        connector = AsyncMock()
        connector.get_last_traded_prices.return_value = {"BTC-USDT": 100}
        result = await self.provider._safe_get_last_traded_prices(connector, ["BTC-USDT"])
        self.assertEqual(result, {"BTC-USDT": 100})
        connector.get_last_traded_prices.side_effect = Exception("Error")
        result = await self.provider._safe_get_last_traded_prices(connector, ["BTC-USDT"])
        self.assertEqual(result, {})
