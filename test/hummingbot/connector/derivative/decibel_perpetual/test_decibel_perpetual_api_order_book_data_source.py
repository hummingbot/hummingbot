import asyncio
import time
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_api_order_book_data_source import (
    DecibelPerpetualAPIOrderBookDataSource,
)
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class TestDecibelPerpetualAPIOrderBookDataSource(TestCase):
    def setUp(self):
        self.trading_pairs = ["BTC-USD"]
        self.connector = MagicMock()
        self.connector.market_address_associated_to_pair = AsyncMock(return_value="0xMARKET")
        self.connector.trading_pair_associated_to_market_address = AsyncMock(return_value="BTC-USD")
        self.connector.convert_from_exchange_trading_pair = MagicMock(return_value="BTC-USD")
        self.connector.get_last_traded_price = AsyncMock(return_value=50000)
        self.connector.authenticator = MagicMock()
        self.connector.authenticator.ws_headers = {"Sec-WebSocket-Protocol": "decibel, token"}

        self.api_factory = MagicMock()
        self.rest_assistant = AsyncMock()
        self.api_factory.get_rest_assistant = AsyncMock(return_value=self.rest_assistant)

        self.data_source = DecibelPerpetualAPIOrderBookDataSource(
            trading_pairs=self.trading_pairs,
            connector=self.connector,
            api_factory=self.api_factory,
        )

    def test_order_book_snapshot_parses_bids_and_asks(self):
        mock_response = {
            "data": {
                "timestamp": int(time.time() * 1000),
                "sequence": 123,
                "bids": [["50000.0", "1.5"], ["49999.0", "2.0"]],
                "asks": [["50001.0", "1.0"], ["50002.0", "3.0"]],
            }
        }
        self.rest_assistant.execute_request = AsyncMock(return_value=mock_response)

        snapshot = asyncio.get_event_loop().run_until_complete(self.data_source._order_book_snapshot("BTC-USD"))
        self.assertEqual(snapshot.type, OrderBookMessageType.SNAPSHOT)
        self.assertEqual(snapshot.content["trading_pair"], "BTC-USD")
        self.assertEqual(snapshot.content["update_id"], 123)
        self.assertEqual(snapshot.content["bids"][0][0], 50000.0)
        self.assertEqual(snapshot.content["asks"][0][0], 50001.0)

    def test_get_last_traded_prices_parses_mark_price(self):
        mock_response = [
            {"market_name": "BTC-USD", "mark_price": "50000.0"},
        ]
        self.rest_assistant.execute_request = AsyncMock(return_value=mock_response)
        prices = asyncio.get_event_loop().run_until_complete(self.data_source.get_last_traded_prices(["BTC-USD"]))
        self.assertEqual(prices["BTC-USD"], 50000.0)

    def test_channel_originating_message_routes_by_topic(self):
        ob = {"topic": "depth:0xMARKET", "data": {}}
        trades = {"topic": "trades:0xMARKET", "data": {}}
        price = {"topic": "market_price:0xMARKET", "data": {}}

        self.assertEqual(self.data_source._channel_originating_message(ob), self.data_source._diff_messages_queue_key)
        self.assertEqual(self.data_source._channel_originating_message(trades), self.data_source._trade_messages_queue_key)
        self.assertEqual(self.data_source._channel_originating_message(price), self.data_source._funding_info_messages_queue_key)

    def test_parse_trade_message_creates_trade_order_book_message(self):
        raw = {
            "topic": "trades:0xMARKET",
            "data": {
                "id": 12345,
                "side": "buy",
                "price": "50000.0",
                "size": "0.5",
                "transaction_unix_ms": int(time.time() * 1000),
            },
        }
        queue = asyncio.Queue()
        asyncio.get_event_loop().run_until_complete(self.data_source._parse_trade_message(raw, queue))

        msg = queue.get_nowait()
        self.assertEqual(msg.type, OrderBookMessageType.TRADE)
        self.assertEqual(msg.content["trading_pair"], "BTC-USD")
        self.assertEqual(msg.content["price"], 50000.0)
        self.assertEqual(msg.content["amount"], 0.5)
