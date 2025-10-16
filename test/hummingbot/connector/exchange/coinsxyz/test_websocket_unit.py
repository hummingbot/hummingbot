#!/usr/bin/env python3
"""
Unit Tests for Coins.xyz WebSocket Components - Day 19 Implementation

This unit test suite validates the WebSocket message parsing and
connection management components with proper mocking.
"""

import time
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.exchange.coinsxyz.coinsxyz_websocket_connection_manager import (
    CoinsxyzWebSocketConnectionManager,
)

# Local imports
from hummingbot.connector.exchange.coinsxyz.coinsxyz_websocket_message_parser import CoinsxyzWebSocketMessageParser


class TestCoinsxyzWebSocketMessageParser(unittest.TestCase):
    """Unit tests for CoinsxyzWebSocketMessageParser."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = CoinsxyzWebSocketMessageParser()

    def test_init(self):
        """Test parser initialization."""
        self.assertIsNotNone(self.parser)

    def test_parse_balance_update(self):
        """Test balance update parsing."""
        balance_message = {
            "outboundAccountPosition": {
                "B": [
                    {"a": "BTC", "f": "1.0", "l": "0.5"},
                    {"a": "USDT", "f": "1000.0", "l": "100.0"}
                ]
            },
            "E": int(time.time() * 1000)
        }

        parsed = self.parser._parse_balance_update(balance_message)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["type"], "balance_update")
        self.assertIn("balances", parsed)
        self.assertEqual(len(parsed["balances"]), 2)

        # Check first balance
        btc_balance = parsed["balances"][0]
        self.assertEqual(btc_balance["asset"], "BTC")
        self.assertEqual(btc_balance["free"], Decimal("1.0"))
        self.assertEqual(btc_balance["locked"], Decimal("0.5"))

    def test_parse_order_update(self):
        """Test order update parsing."""
        order_message = {
            "executionReport": {
                "i": "12345",
                "c": "client_order_123",
                "s": "BTCUSDT",
                "S": "BUY",
                "o": "LIMIT",
                "X": "NEW",
                "q": "1.0",
                "p": "50000.0",
                "z": "0.0",
                "Z": "0.0"
            },
            "E": int(time.time() * 1000)
        }

        parsed = self.parser._parse_order_update(order_message)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["type"], "order_update")
        self.assertEqual(parsed["order_id"], "12345")
        self.assertEqual(parsed["client_order_id"], "client_order_123")
        self.assertEqual(parsed["symbol"], "BTCUSDT")
        self.assertEqual(parsed["side"], "BUY")
        self.assertEqual(parsed["status"], "NEW")
        self.assertEqual(parsed["quantity"], Decimal("1.0"))
        self.assertEqual(parsed["price"], Decimal("50000.0"))

    def test_parse_trade_update(self):
        """Test trade update parsing."""
        trade_message = {
            "trade": {
                "t": "67890",
                "i": "12345",
                "s": "BTCUSDT",
                "S": "BUY",
                "q": "1.0",
                "p": "50000.0",
                "n": "0.1",
                "N": "BNB"
            },
            "E": int(time.time() * 1000)
        }

        parsed = self.parser._parse_trade_update(trade_message)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["type"], "trade_update")
        self.assertEqual(parsed["trade_id"], "67890")
        self.assertEqual(parsed["order_id"], "12345")
        self.assertEqual(parsed["symbol"], "BTCUSDT")
        self.assertEqual(parsed["side"], "BUY")
        self.assertEqual(parsed["quantity"], Decimal("1.0"))
        self.assertEqual(parsed["price"], Decimal("50000.0"))
        self.assertEqual(parsed["commission"], Decimal("0.1"))
        self.assertEqual(parsed["commission_asset"], "BNB")

    def test_parse_user_stream_message(self):
        """Test user stream message parsing."""
        # Test balance update
        balance_msg = {
            "outboundAccountPosition": {
                "B": [{"a": "BTC", "f": "1.0", "l": "0.5"}]
            }
        }

        parsed = self.parser.parse_user_stream_message(balance_msg)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["type"], "balance_update")

        # Test order update
        order_msg = {
            "executionReport": {
                "i": "12345",
                "X": "FILLED"
            }
        }

        parsed = self.parser.parse_user_stream_message(order_msg)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["type"], "order_update")

        # Test trade update
        trade_msg = {
            "trade": {
                "t": "67890",
                "i": "12345"
            }
        }

        parsed = self.parser.parse_user_stream_message(trade_msg)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["type"], "trade_update")

    def test_parse_invalid_message(self):
        """Test parsing of invalid messages."""
        # Test None message
        parsed = self.parser.parse_user_stream_message(None)
        self.assertIsNone(parsed)

        # Test empty message
        parsed = self.parser.parse_user_stream_message({})
        self.assertIsNone(parsed)

        # Test invalid message format
        parsed = self.parser.parse_user_stream_message({"invalid": "data"})
        self.assertIsNone(parsed)

    def test_process_balance_event(self):
        """Test balance event processing."""
        balance_data = {
            'timestamp': int(time.time() * 1000),
            'balances': [
                {'asset': 'BTC', 'free': '1.0', 'locked': '0.5'}
            ]
        }

        processed = self.parser._process_balance_event(balance_data)

        self.assertIsNotNone(processed)
        self.assertEqual(processed['event_type'], 'balance_update')
        self.assertIn('processed_at', processed)
        self.assertEqual(processed['balances'], balance_data['balances'])

    def test_process_order_event(self):
        """Test order event processing."""
        order_data = {
            'timestamp': int(time.time() * 1000),
            'order_id': '12345',
            'status': 'FILLED'
        }

        processed = self.parser._process_order_event(order_data)

        self.assertIsNotNone(processed)
        self.assertEqual(processed['event_type'], 'order_update')
        self.assertIn('processed_at', processed)
        self.assertEqual(processed['order_id'], '12345')
        self.assertEqual(processed['status'], 'FILLED')

    def test_process_trade_event(self):
        """Test trade event processing."""
        trade_data = {
            'timestamp': int(time.time() * 1000),
            'trade_id': '67890',
            'quantity': '1.0',
            'price': '50000.0'
        }

        processed = self.parser._process_trade_event(trade_data)

        self.assertIsNotNone(processed)
        self.assertEqual(processed['event_type'], 'trade_execution')
        self.assertIn('processed_at', processed)
        self.assertEqual(processed['trade_id'], '67890')


class TestCoinsxyzWebSocketConnectionManager(unittest.TestCase):
    """Unit tests for CoinsxyzWebSocketConnectionManager."""

    def setUp(self):
        """Set up test fixtures."""
        self.connection_manager = CoinsxyzWebSocketConnectionManager()

    def test_init(self):
        """Test connection manager initialization."""
        self.assertIsNotNone(self.connection_manager)
        self.assertFalse(self.connection_manager.is_connected)

    def test_connection_state_property(self):
        """Test connection state property."""
        from hummingbot.connector.exchange.coinsxyz.coinsxyz_websocket_connection_manager import ConnectionState

        initial_state = self.connection_manager.connection_state
        self.assertEqual(initial_state, ConnectionState.DISCONNECTED)

    @patch('asyncio.create_task')
    async def test_start(self, mock_create_task):
        """Test connection manager start."""
        mock_create_task.return_value = MagicMock()

        await self.connection_manager.start()

        # Should create background tasks
        self.assertTrue(mock_create_task.called)

    async def test_stop(self):
        """Test connection manager stop."""
        # Mock some internal state
        self.connection_manager._shutdown_event = AsyncMock()
        self.connection_manager._ws_assistant = MagicMock()
        self.connection_manager._ws_assistant.disconnect = AsyncMock()

        await self.connection_manager.stop()

        # Should call shutdown
        self.connection_manager._shutdown_event.set.assert_called_once()

    async def test_connect(self):
        """Test WebSocket connection."""
        with patch.object(self.connection_manager, '_connect', new_callable=AsyncMock) as mock_connect:
            await self.connection_manager.connect()
            mock_connect.assert_called_once()

    async def test_disconnect(self):
        """Test WebSocket disconnection."""
        with patch.object(self.connection_manager, '_disconnect', new_callable=AsyncMock) as mock_disconnect:
            await self.connection_manager.disconnect()
            mock_disconnect.assert_called_once()

    async def test_handle_user_stream_message(self):
        """Test user stream message handling."""
        test_message = {
            'stream': 'user_stream',
            'data': {
                'outboundAccountPosition': {
                    'B': [{'a': 'BTC', 'f': '1.0', 'l': '0.5'}]
                }
            }
        }

        with patch.object(self.connection_manager, '_handle_balance_update', new_callable=AsyncMock) as mock_handle:
            await self.connection_manager._handle_user_stream_message(test_message)
            mock_handle.assert_called_once()

    def test_get_subscription_count(self):
        """Test subscription count."""
        count = self.connection_manager.get_subscription_count()
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
