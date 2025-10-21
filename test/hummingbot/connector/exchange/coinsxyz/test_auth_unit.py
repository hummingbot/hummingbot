#!/usr/bin/env python3
"""
Unit Tests for Coins.xyz Authentication - Day 19 Implementation

This unit test suite validates the authentication components
of the Coins.xyz connector with proper mocking and isolation.
"""

import time
import unittest
from unittest.mock import MagicMock

# Local imports
from hummingbot.connector.exchange.coinsxyz.coinsxyz_auth import CoinsxyzAuth
from hummingbot.connector.time_synchronizer import TimeSynchronizer


class TestCoinsxyzAuth(unittest.TestCase):
    """Unit tests for CoinsxyzAuth authentication."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key_12345"
        self.secret_key = "test_secret_key_67890"
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
        params = {"symbol": "BTCUSDT", "side": "BUY", "type": "LIMIT", "quantity": 1, "price": 50000, "timestamp": int(time.time() * 1000)}

        signature = self.auth._generate_signature(params)

        self.assertIsInstance(signature, str)
        self.assertTrue(len(signature) > 0)

        # Test signature consistency
        signature2 = self.auth._generate_signature(params)
        self.assertEqual(signature, signature2)

    def test_signature_uniqueness(self):
        """Test that different inputs produce different signatures."""
        timestamp = int(time.time() * 1000)

        sig1 = self.auth._generate_signature({"param1": "value1", "timestamp": timestamp})
        sig2 = self.auth._generate_signature({"param1": "value2", "timestamp": timestamp})

        self.assertNotEqual(sig1, sig2)

    def test_rest_authenticate(self):
        """Test REST API authentication."""
        import asyncio
        request = MagicMock()
        request.params = {"symbol": "BTCUSDT"}
        request.headers = {}
        request.method = MagicMock()

        authenticated_request = asyncio.run(self.auth.rest_authenticate(request))

        self.assertIsNotNone(authenticated_request)
        self.assertIn("timestamp", authenticated_request.params)
        self.assertIn("signature", authenticated_request.params)
        self.assertEqual(authenticated_request.headers.get("X-COINS-APIKEY"), self.api_key)

    def test_ws_authenticate(self):
        """Test WebSocket authentication."""
        import asyncio
        request = MagicMock()

        authenticated_request = asyncio.run(self.auth.ws_authenticate(request))

        self.assertIsNotNone(authenticated_request)
        # WebSocket auth would add specific headers/params

    def test_header_for_authentication(self):
        """Test authentication headers."""
        headers = self.auth.header_for_authentication()

        self.assertIn("X-COINS-APIKEY", headers)
        self.assertEqual(headers["X-COINS-APIKEY"], self.api_key)
        self.assertIn("User-Agent", headers)

    def test_is_timestamp_valid(self):
        """Test timestamp validation."""
        current_time = int(time.time() * 1000)

        # Valid timestamp (within 5 minutes)
        valid_timestamp = current_time - 3000
        self.assertTrue(self.auth.is_timestamp_valid(valid_timestamp))

        # Invalid timestamp (too old - more than 5 minutes)
        invalid_timestamp = current_time - 400000
        self.assertFalse(self.auth.is_timestamp_valid(invalid_timestamp))

    def test_signature_with_empty_params(self):
        """Test signature generation with empty parameters."""
        timestamp = int(time.time() * 1000)
        signature = self.auth._generate_signature({"timestamp": timestamp})

        self.assertIsInstance(signature, str)
        self.assertTrue(len(signature) > 0)

    def test_signature_with_special_characters(self):
        """Test signature generation with special characters."""
        timestamp = int(time.time() * 1000)
        params = {"symbol": "BTC-USDT", "side": "BUY", "price": "50,000.00", "timestamp": timestamp}

        signature = self.auth._generate_signature(params)

        self.assertIsInstance(signature, str)
        self.assertTrue(len(signature) > 0)

    def test_authentication_with_none_params(self):
        """Test authentication with None parameters."""
        import asyncio
        request = MagicMock()
        request.params = None
        request.headers = {}
        request.data = None
        request.method = MagicMock()

        # Should handle None params gracefully
        try:
            authenticated_request = asyncio.run(self.auth.rest_authenticate(request))
            self.assertIsNotNone(authenticated_request)
        except Exception as e:
            self.fail(f"Authentication failed with None params: {e}")

    def test_multiple_authentications(self):
        """Test multiple authentication calls."""
        import asyncio
        request1 = MagicMock()
        request1.params = {"symbol": "BTCUSDT"}
        request1.headers = {}
        request1.method = MagicMock()

        request2 = MagicMock()
        request2.params = {"symbol": "BTCUSDT"}
        request2.headers = {}
        request2.method = MagicMock()

        # Multiple authentications should work
        auth1 = asyncio.run(self.auth.rest_authenticate(request1))
        time.sleep(0.001)
        auth2 = asyncio.run(self.auth.rest_authenticate(request2))

        self.assertIsNotNone(auth1)
        self.assertIsNotNone(auth2)

        # Signatures should be different due to different timestamps
        self.assertNotEqual(
            auth1.params.get("signature"),
            auth2.params.get("signature")
        )


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

    def test_timestamp_consistency(self):
        """Test timestamp consistency over short periods."""
        timestamp1 = self.time_sync.time_ms()
        time.sleep(0.001)  # 1ms delay
        timestamp2 = self.time_sync.time_ms()

        self.assertGreaterEqual(timestamp2, timestamp1)
        self.assertLess(timestamp2 - timestamp1, 100)  # Should be less than 100ms difference


if __name__ == "__main__":
    unittest.main()
