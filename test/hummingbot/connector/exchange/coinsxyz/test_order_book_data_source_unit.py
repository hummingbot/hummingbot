#!/usr/bin/env python3
"""
Unit Tests for Coins.xyz Order Book Data Source
"""

import unittest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

from hummingbot.connector.exchange.coinsxyz.coinsxyz_api_order_book_data_source import CoinsxyzAPIOrderBookDataSource
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class TestCoinsxyzAPIOrderBookDataSource(unittest.TestCase):
    """Unit tests for CoinsxyzAPIOrderBookDataSource."""

    def setUp(self):
        """Set up test fixtures."""
        self.trading_pairs = ["BTC-USDT", "ETH-USDT"]
        self.connector = MagicMock()
        self.api_factory = MagicMock()

        self.data_source = CoinsxyzAPIOrderBookDataSource(
            trading_pairs=self.trading_pairs,
            connector=self.connector,
            api_factory=self.api_factory
        )

    def test_init(self):
        """Test data source initialization."""
        self.assertEqual(self.data_source._trading_pairs, self.trading_pairs)
        self.assertIsNotNone(self.data_source._connector)

    @patch('hummingbot.connector.exchange.coinsxyz.coinsxyz_api_order_book_data_source.CoinsxyzAPIOrderBookDataSource._order_book_snapshot')
    async def test_get_order_book_snapshot(self, mock_snapshot):
        """Test order book snapshot retrieval."""
        mock_snapshot.return_value = MagicMock(spec=OrderBookMessage)

        snapshot = await self.data_source.get_order_book_snapshot("BTC-USDT")

        self.assertIsNotNone(snapshot)
        mock_snapshot.assert_called_once_with("BTC-USDT")

    async def test_order_book_snapshot(self):
        """Test order book snapshot parsing."""
        mock_rest_assistant = AsyncMock()
        mock_rest_assistant.execute_request.return_value = {
            "lastUpdateId": 12345,
            "bids": [["50000.0", "1.0"], ["49999.0", "2.0"]],
            "asks": [["50001.0", "1.5"], ["50002.0", "2.5"]]
        }

        self.api_factory.get_rest_assistant = AsyncMock(return_value=mock_rest_assistant)

        snapshot = await self.data_source._order_book_snapshot("BTC-USDT")

        self.assertEqual(snapshot.type, OrderBookMessageType.SNAPSHOT)
        self.assertEqual(snapshot.content["trading_pair"], "BTC-USDT")
        self.assertEqual(len(snapshot.content["bids"]), 2)
        self.assertEqual(len(snapshot.content["asks"]), 2)

    async def test_parse_trade_message(self):
        """Test trade message parsing."""
        raw_message = {
            "stream": "btcusdt@trade",
            "data": {
                "e": "trade",
                "s": "BTCUSDT",
                "t": 12345,
                "p": "50000.0",
                "q": "1.0",
                "T": 1234567890000,
                "m": False
            }
        }

        queue = asyncio.Queue()
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="BTC-USDT")

        await self.data_source._parse_trade_message(raw_message, queue)

        self.assertFalse(queue.empty())
        message = await queue.get()
        self.assertEqual(message.type, OrderBookMessageType.TRADE)

    async def test_parse_order_book_diff_message(self):
        """Test order book diff message parsing."""
        raw_message = {
            "e": "depthUpdate",
            "s": "BTCUSDT",
            "U": 12345,
            "u": 12346,
            "b": [["50000.0", "1.0"]],
            "a": [["50001.0", "1.5"]]
        }

        queue = asyncio.Queue()
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="BTC-USDT")

        await self.data_source._parse_order_book_diff_message(raw_message, queue)

        self.assertFalse(queue.empty())

    @patch('hummingbot.connector.exchange.coinsxyz.coinsxyz_api_order_book_data_source.CoinsxyzAPIOrderBookDataSource._connected_websocket_assistant')
    async def test_listen_for_order_book_diffs(self, mock_ws):
        """Test order book diff listener."""
        mock_ws_assistant = AsyncMock()
        mock_ws_assistant.iter_messages = AsyncMock()
        mock_ws.return_value = mock_ws_assistant

        output_queue = asyncio.Queue()

        # Test with timeout to avoid infinite loop
        try:
            await asyncio.wait_for(
                self.data_source.listen_for_order_book_diffs(asyncio.get_event_loop(), output_queue),
                timeout=0.1
            )
        except asyncio.TimeoutError:
            pass

        mock_ws.assert_called()

    @patch('hummingbot.connector.exchange.coinsxyz.coinsxyz_api_order_book_data_source.CoinsxyzAPIOrderBookDataSource._order_book_snapshot')
    async def test_listen_for_order_book_snapshots(self, mock_snapshot):
        """Test order book snapshot listener."""
        mock_snapshot.return_value = MagicMock(spec=OrderBookMessage)

        output_queue = asyncio.Queue()

        # Test with timeout
        try:
            await asyncio.wait_for(
                self.data_source.listen_for_order_book_snapshots(asyncio.get_event_loop(), output_queue),
                timeout=0.1
            )
        except asyncio.TimeoutError:
            pass

        self.assertFalse(output_queue.empty())


if __name__ == "__main__":
    unittest.main()
