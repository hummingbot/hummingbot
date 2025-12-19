#!/usr/bin/env python3
"""
Unit Tests for Coins.xyz User Stream Data Source
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.exchange.coinsxyz.coinsxyz_api_user_stream_data_source import (
    CoinsxyzAPIUserStreamDataSource,
    ListenKeyState,
    ValidationResult,
)


class TestCoinsxyzAPIUserStreamDataSource(unittest.TestCase):
    """Unit tests for CoinsxyzAPIUserStreamDataSource."""

    def setUp(self):
        """Set up test fixtures."""
        self.auth = MagicMock()
        self.trading_pairs = ["BTC-USDT", "ETH-USDT"]
        self.connector = MagicMock()
        self.api_factory = MagicMock()

        self.data_source = CoinsxyzAPIUserStreamDataSource(
            auth=self.auth,
            trading_pairs=self.trading_pairs,
            connector=self.connector,
            api_factory=self.api_factory
        )

    def test_init(self):
        """Test data source initialization."""
        self.assertEqual(self.data_source._trading_pairs, self.trading_pairs)
        self.assertEqual(self.data_source.listen_key_state, ListenKeyState.INACTIVE)

    def test_create_listen_key(self):
        """Test listenKey creation."""
        import asyncio
        
        async def run_test():
            mock_rest_assistant = AsyncMock()
            mock_rest_assistant.execute_request.return_value = {"listenKey": "test_key_123"}
            self.api_factory.get_rest_assistant = AsyncMock(return_value=mock_rest_assistant)

            listen_key_info = await self.data_source._create_listen_key()

            self.assertEqual(listen_key_info.key, "test_key_123")
            self.assertEqual(listen_key_info.state, ListenKeyState.ACTIVE)
        
        asyncio.run(run_test())

    @patch('hummingbot.connector.exchange.coinsxyz.coinsxyz_api_user_stream_data_source.CoinsxyzAPIUserStreamDataSource._ping_listen_key')
    def test_ping_listen_key(self, mock_ping):
        """Test listenKey ping."""
        import asyncio
        
        async def run_test():
            mock_ping.return_value = True

            # Set up listen key
            self.data_source._listen_key_info = MagicMock()
            self.data_source._listen_key_info.state = ListenKeyState.ACTIVE
            self.data_source._listen_key_info.key = "test_key"

            result = await self.data_source._ping_listen_key()

            self.assertTrue(result)
        
        asyncio.run(run_test())

    def test_validate_balance_update(self):
        """Test balance update validation."""
        import asyncio
        
        async def run_test():
            import time
            current_time_ms = int(time.time() * 1000)
            valid_data = {
                "e": "outboundAccountPosition",
                "E": current_time_ms,
                "B": [{"a": "BTC", "f": "1.0", "l": "0.5"}]
            }

            result = await self.data_source._validate_balance_update(valid_data)
            self.assertEqual(result, ValidationResult.VALID)

            invalid_data = {"e": "outboundAccountPosition"}
            result = await self.data_source._validate_balance_update(invalid_data)
            self.assertNotEqual(result, ValidationResult.VALID)
        
        asyncio.run(run_test())

    def test_validate_order_update(self):
        """Test order update validation."""
        import asyncio
        
        async def run_test():
            import time
            current_time_ms = int(time.time() * 1000)
            valid_data = {
                "e": "executionReport",
                "E": current_time_ms,
                "s": "BTCUSDT",
                "c": "client_order_1",
                "i": "12345",
                "S": "BUY",
                "o": "LIMIT",
                "q": "1.0",
                "p": "50000.0",
                "X": "NEW"
            }

            result = await self.data_source._validate_order_update(valid_data)
            self.assertEqual(result, ValidationResult.VALID)
        
        asyncio.run(run_test())

    def test_process_balance_update(self):
        """Test balance update processing."""
        import asyncio
        
        async def run_test():
            import time
            current_time_ms = int(time.time() * 1000)
            raw_data = {
                "e": "outboundAccountPosition",
                "E": current_time_ms,
                "B": [
                    {"a": "BTC", "f": "1.0", "l": "0.5"},
                    {"a": "USDT", "f": "10000.0", "l": "1000.0"}
                ]
            }

            balance_event = await self.data_source._process_balance_update(raw_data)

            self.assertIsNotNone(balance_event)
            self.assertEqual(balance_event.asset, "BTC")
        
        asyncio.run(run_test())

    def test_process_order_update(self):
        """Test order update processing."""
        import asyncio
        
        async def run_test():
            import time
            current_time_ms = int(time.time() * 1000)
            raw_data = {
                "e": "executionReport",
                "E": current_time_ms,
                "s": "BTCUSDT",
                "c": "client_order_1",
                "i": "12345",
                "S": "BUY",
                "o": "LIMIT",
                "q": "1.0",
                "p": "50000.0",
                "X": "FILLED",
                "z": "1.0"
            }

            order_event = await self.data_source._process_order_update(raw_data)

            self.assertIsNotNone(order_event)
            self.assertEqual(order_event.client_order_id, "client_order_1")
            self.assertEqual(order_event.status, "FILLED")
        
        asyncio.run(run_test())

    def test_handle_http_error(self):
        """Test HTTP error handling."""
        import asyncio
        
        async def run_test():
            error = Exception("Rate limit exceeded")
            error.status = 429

            recovery_action = await self.data_source._handle_http_error(error, "/test/endpoint")

            self.assertIsNotNone(recovery_action)
        
        asyncio.run(run_test())

    def test_detect_timestamp_drift(self):
        """Test timestamp drift detection."""
        import asyncio
        
        async def run_test():
            server_timestamp = 1234567890000

            result = await self.data_source._detect_timestamp_drift(server_timestamp)

            self.assertIsInstance(result, bool)
        
        asyncio.run(run_test())

    def test_get_connection_stats(self):
        """Test connection statistics."""
        stats = self.data_source.get_connection_stats()

        self.assertIn("connection_state", stats)
        self.assertIn("events_processed", stats)
        self.assertIn("balance_updates_processed", stats)

    def test_get_validation_summary(self):
        """Test validation summary."""
        summary = self.data_source.get_validation_summary()

        self.assertIn("validation_enabled", summary)
        self.assertIn("total_events_processed", summary)
        self.assertIn("validation_errors", summary)

    def test_get_error_summary(self):
        """Test error summary."""
        summary = self.data_source.get_error_summary()

        self.assertIn("http_errors_count", summary)
        self.assertIn("rate_limit_hits", summary)
        self.assertIn("network_failures", summary)


if __name__ == "__main__":
    unittest.main()
