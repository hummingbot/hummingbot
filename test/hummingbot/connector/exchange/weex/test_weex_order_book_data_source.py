"""
Unit tests for WEEX order book data source (public WS)
"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.exchange.weex.weex_api_order_book_data_source import WeexAPIOrderBookDataSource
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class TestWeexOrderBookDataSource(unittest.TestCase):
    """Test WEEX public market data (order book, trades)"""

    def setUp(self):
        self.connector = MagicMock()
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="VCCUSDT-SPBL")
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="VCC-USDT")

        self.api_factory = MagicMock()
        self.trading_pairs = ["VCC-USDT"]

        self.data_source = WeexAPIOrderBookDataSource(
            trading_pairs=self.trading_pairs,
            connector=self.connector,
            api_factory=self.api_factory,
            domain="com",
        )

    def test_snapshot_message_parsing(self):
        """Test parsing order book snapshot from WEEX API response"""
        from hummingbot.connector.exchange.weex.weex_order_book import WeexOrderBook

        snapshot = {
            "data": {
                "bids": [["0.00015", "100000"]],
                "asks": [["0.00016", "100000"]],
            },
            "requestTime": 1234567890,
            "trading_pair": "VCC-USDT",
        }

        message = WeexOrderBook.snapshot_message_from_exchange(snapshot, timestamp=1000.0)

        self.assertEqual(message.type, OrderBookMessageType.SNAPSHOT)
        self.assertEqual(message.trading_pair, "VCC-USDT")
        self.assertIn("bids", message.content)
        self.assertIn("asks", message.content)
        self.assertEqual(len(message.content["bids"]), 1)
        self.assertEqual(len(message.content["asks"]), 1)

    def test_diff_message_parsing(self):
        """Test parsing order book diff (updates) from WS"""
        from hummingbot.connector.exchange.weex.weex_order_book import WeexOrderBook

        diff = {
            "bids": [{"price": "0.00015", "size": "50000"}],
            "asks": [{"price": "0.00016", "size": "50000"}],
            "startVersion": 100,
            "endVersion": 101,
            "symbol": "VCCUSDT-SPBL",
            "trading_pair": "VCC-USDT",
        }

        message = WeexOrderBook.diff_message_from_exchange(diff, timestamp=1000.0)

        self.assertEqual(message.type, OrderBookMessageType.DIFF)
        self.assertEqual(message.trading_pair, "VCC-USDT")
        self.assertEqual(message.first_update_id, 100)
        self.assertEqual(message.update_id, 101)

    def test_trade_message_parsing(self):
        """Test parsing trade event from WS"""
        from hummingbot.connector.exchange.weex.weex_order_book import WeexOrderBook

        trade = {
            "price": "0.00015",
            "size": "1000",
            "time": 1000000,
            "buyerMaker": False,
            "tradeId": "trade123",
            "trading_pair": "VCC-USDT",
        }

        message = WeexOrderBook.trade_message_from_exchange(trade)

        self.assertEqual(message.type, OrderBookMessageType.TRADE)
        self.assertEqual(message.trading_pair, "VCC-USDT")
        self.assertEqual(float(message.content["price"]), 0.00015)
        self.assertEqual(float(message.content["amount"]), 1000)

    def test_channel_originating_message(self):
        """Test message channel detection"""
        depth_msg = {
            "event": "payload",
            "channel": "depth.VCCUSDT-SPBL.15",
            "data": [],
        }

        channel = self.data_source._channel_originating_message(depth_msg)
        self.assertEqual(channel, "diff")

        trade_msg = {
            "event": "payload",
            "channel": "trades.VCCUSDT-SPBL",
            "data": [],
        }

        channel = self.data_source._channel_originating_message(trade_msg)
        self.assertEqual(channel, "trade")

    @patch("aiohttp.ClientSession")
    async def test_order_book_snapshot_fetch(self, mock_session):
        """Test fetching initial order book snapshot via REST"""
        mock_response = MagicMock()
        mock_response.json = AsyncMock(
            return_value={
                "code": "00000",
                "data": {"bids": [["0.00015", "100000"]], "asks": [["0.00016", "100000"]]},
            }
        )

        mock_session.return_value.get = AsyncMock(return_value=mock_response)

        # Mock the REST assistant
        mock_rest_assistant = AsyncMock()
        mock_rest_assistant.execute_request = AsyncMock(
            return_value={
                "code": "00000",
                "data": {"bids": [["0.00015", "100000"]], "asks": [["0.00016", "100000"]]},
            }
        )
        self.api_factory.get_rest_assistant = AsyncMock(return_value=mock_rest_assistant)

        result = await self.data_source._request_order_book_snapshot("VCC-USDT")
        self.assertIsNotNone(result)


class TestWeexOrderBook(unittest.TestCase):
    """Test WEEX order book message construction"""

    def test_order_book_snapshot_message_content(self):
        """Verify snapshot message has correct structure"""
        from hummingbot.connector.exchange.weex.weex_order_book import WeexOrderBook

        snapshot = {
            "data": {
                "bids": [["0.00015", "100000"], ["0.00014", "50000"]],
                "asks": [["0.00016", "100000"], ["0.00017", "50000"]],
            },
            "requestTime": 1234567890,
            "trading_pair": "VCC-USDT",
        }

        message = WeexOrderBook.snapshot_message_from_exchange(snapshot, timestamp=1000.0)

        self.assertEqual(len(message.content["bids"]), 2)
        self.assertEqual(len(message.content["asks"]), 2)
        self.assertEqual(message.content["bids"][0], ["0.00015", "100000"])

    def test_trade_message_buy_sell_detection(self):
        """Verify trade direction is correctly detected"""
        from hummingbot.connector.exchange.weex.weex_order_book import WeexOrderBook
        from hummingbot.core.data_type.common import TradeType

        # buyerMaker=False means taker was buyer (sell-initiated trade)
        sell_trade = {
            "price": "0.00015",
            "size": "1000",
            "time": 1000000,
            "buyerMaker": False,
            "tradeId": "trade1",
            "trading_pair": "VCC-USDT",
        }

        message = WeexOrderBook.trade_message_from_exchange(sell_trade)
        self.assertEqual(message.content["trade_type"], float(TradeType.BUY.value))

        # buyerMaker=True means taker was seller (buy-initiated trade)
        buy_trade = {
            "price": "0.00015",
            "size": "1000",
            "time": 1000000,
            "buyerMaker": True,
            "tradeId": "trade2",
            "trading_pair": "VCC-USDT",
        }

        message = WeexOrderBook.trade_message_from_exchange(buy_trade)
        self.assertEqual(message.content["trade_type"], float(TradeType.SELL.value))


if __name__ == "__main__":
    unittest.main()
