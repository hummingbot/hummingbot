#!/usr/bin/env python3
"""
Unit Tests for Coins.xyz Connector - Day 19 Implementation

This comprehensive unit test suite validates individual components
of the Coins.xyz connector with proper mocking and isolation.
"""

import unittest
import time
from unittest.mock import MagicMock

# Local imports
from hummingbot.connector.exchange.coinsxyz.coinsxyz_auth import CoinsxyzAuth
from hummingbot.connector.exchange.coinsxyz.coinsxyz_retry_utils import CoinsxyzRetryHandler, RetryConfigs
from hummingbot.connector.exchange.coinsxyz.coinsxyz_websocket_message_parser import CoinsxyzWebSocketMessageParser
from hummingbot.connector.time_synchronizer import TimeSynchronizer


class TestCoinsxyzAuth(unittest.TestCase):
    """Unit tests for CoinsxyzAuth authentication."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key"
        self.secret_key = "test_secret_key"
        self.time_provider = TimeSynchronizer()
        self.auth = CoinsxyzAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self.time_provider
        )

    def test_init(self):
        """Test authentication initialization."""
        self.assertEqual(self.auth.api_key, self.api_key)
        self.assertEqual(self.auth.secret_key, self.secret_key)
        self.assertIsNotNone(self.auth.time_provider)

    def test_generate_signature(self):
        """Test HMAC signature generation."""
        query_string = "symbol=BTCUSDT&side=BUY&type=LIMIT&quantity=1&price=50000"
        timestamp = int(time.time() * 1000)

        signature = self.auth._generate_signature(query_string, timestamp)

        self.assertIsInstance(signature, str)
        self.assertTrue(len(signature) > 0)

        # Test signature consistency
        signature2 = self.auth._generate_signature(query_string, timestamp)
        self.assertEqual(signature, signature2)

    def test_rest_authenticate(self):
        """Test REST API authentication."""
        request = MagicMock()
        request.params = {"symbol": "BTCUSDT"}

        authenticated_request = self.auth.rest_authenticate(request)

        self.assertIsNotNone(authenticated_request)
        self.assertIn("timestamp", authenticated_request.params)
        self.assertIn("signature", authenticated_request.params)
        self.assertEqual(authenticated_request.headers.get("X-MBX-APIKEY"), self.api_key)

    def test_ws_authenticate(self):
        """Test WebSocket authentication."""
        request = MagicMock()

        authenticated_request = self.auth.ws_authenticate(request)

        self.assertIsNotNone(authenticated_request)
        # WebSocket auth would add specific headers/params

    def test_header_for_authentication(self):
        """Test authentication headers."""
        headers = self.auth.header_for_authentication()

        self.assertIn("X-MBX-APIKEY", headers)
        self.assertEqual(headers["X-MBX-APIKEY"], self.api_key)
        self.assertIn("User-Agent", headers)

    def test_is_timestamp_valid(self):
        """Test timestamp validation."""
        current_time = int(time.time() * 1000)

        # Valid timestamp (within 5 seconds)
        valid_timestamp = current_time - 3000
        self.assertTrue(self.auth.is_timestamp_valid(valid_timestamp))

        # Invalid timestamp (too old)
        invalid_timestamp = current_time - 10000
        self.assertFalse(self.auth.is_timestamp_valid(invalid_timestamp))


class TestCoinsxyzRetryHandler(unittest.TestCase):
    """Unit tests for CoinsxyzRetryHandler."""

    def setUp(self):
        """Set up test fixtures."""
        self.retry_handler = CoinsxyzRetryHandler(RetryConfigs.STANDARD)

    def test_init(self):
        """Test retry handler initialization."""
        self.assertIsNotNone(self.retry_handler._config)
        self.assertIsInstance(self.retry_handler._retry_stats, dict)

    def test_calculate_backoff_delay(self):
        """Test backoff delay calculation."""
        delay1 = self.retry_handler.calculate_backoff_delay(1)
        delay2 = self.retry_handler.calculate_backoff_delay(2)
        delay3 = self.retry_handler.calculate_backoff_delay(3)

        # Exponential backoff should increase delays
        self.assertGreater(delay2, delay1)
        self.assertGreater(delay3, delay2)

    def test_should_retry_request(self):
        """Test retry decision logic."""
        # Test with retryable exception
        from hummingbot.connector.exchange.coinsxyz.coinsxyz_exceptions import CoinsxyzNetworkError
        network_error = CoinsxyzNetworkError("Connection failed")

        # Should retry on first attempt
        self.assertTrue(self.retry_handler.should_retry_request(network_error, 1))

        # Should not retry after max attempts
        self.assertFalse(self.retry_handler.should_retry_request(network_error, 10))

    def test_handle_rate_limit(self):
        """Test rate limit handling."""
        headers_with_retry_after = {"Retry-After": "60"}
        delay = self.retry_handler.handle_rate_limit(headers_with_retry_after)
        self.assertEqual(delay, 60.0)

        headers_without_retry_after = {}
        delay = self.retry_handler.handle_rate_limit(headers_without_retry_after)
        self.assertGreater(delay, 0)

    def test_handle_network_failure(self):
        """Test network failure handling."""
        exception = Exception("Network timeout")
        delay = self.retry_handler.handle_network_failure(exception)

        self.assertGreater(delay, 0)
        self.assertIsInstance(delay, float)

    def test_recover_connection(self):
        """Test connection recovery."""
        result = self.retry_handler.recover_connection()
        self.assertIsInstance(result, bool)


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
        self.assertEqual(parsed["status"], "NEW")

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


class TestTimeSynchronizer(unittest.TestCase):
    """Unit tests for TimeSynchronizer."""

    def setUp(self):
        """Set up test fixtures."""
        self.time_sync = TimeSynchronizer()

    def test_init(self):
        """Test time synchronizer initialization."""
        self.assertIsNotNone(self.time_sync)

    def test_time_ms(self):
        """Test millisecond timestamp generation."""
        timestamp = self.time_sync.time_ms()

        self.assertIsInstance(timestamp, int)
        self.assertGreater(timestamp, 0)

        # Should be close to current time
        current_time = int(time.time() * 1000)
        self.assertLess(abs(timestamp - current_time), 1000)  # Within 1 second

    def test_get_timestamp(self):
        """Test timestamp generation."""
        timestamp = self.time_sync.get_timestamp()

        self.assertIsInstance(timestamp, int)
        self.assertGreater(timestamp, 0)

    def test_get_time_offset_ms(self):
        """Test time offset calculation."""
        offset = self.time_sync.get_time_offset_ms()

        self.assertIsInstance(offset, (int, float))


if __name__ == "__main__":
    unittest.main()
