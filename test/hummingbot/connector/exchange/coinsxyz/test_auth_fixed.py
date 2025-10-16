#!/usr/bin/env python3
"""
Fixed Unit Tests for Coins.xyz Authentication Module
"""

import unittest
import asyncio
import time

from hummingbot.connector.exchange.coinsxyz.coinsxyz_auth import CoinsxyzAuth
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, RESTMethod, WSRequest


class TestCoinsxyzAuthFixed(unittest.TestCase):
    """Fixed unit tests for CoinsxyzAuth authentication."""

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
        params = {"symbol": "BTCUSDT", "side": "BUY", "type": "LIMIT", "quantity": "1", "price": "50000"}

        signature = self.auth._generate_signature(params)

        self.assertIsInstance(signature, str)
        self.assertTrue(len(signature) > 0)
        self.assertEqual(len(signature), 64)  # SHA256 hex is 64 chars

        # Test signature consistency
        signature2 = self.auth._generate_signature(params)
        self.assertEqual(signature, signature2)

    def test_signature_uniqueness(self):
        """Test that different inputs produce different signatures."""
        params1 = {"symbol": "BTCUSDT", "side": "BUY"}
        params2 = {"symbol": "ETHUSDT", "side": "BUY"}

        sig1 = self.auth._generate_signature(params1)
        sig2 = self.auth._generate_signature(params2)
        self.assertNotEqual(sig1, sig2)

    def test_rest_authenticate_async(self):
        """Test REST API authentication (async)."""
        async def run_test():
            request = RESTRequest(
                method=RESTMethod.GET,
                url="/test",
                params={"symbol": "BTCUSDT"}
            )

            authenticated_request = await self.auth.rest_authenticate(request)

            self.assertIsNotNone(authenticated_request)
            self.assertIn("timestamp", authenticated_request.params)
            self.assertIn("signature", authenticated_request.params)
            self.assertEqual(authenticated_request.headers.get("X-COINS-APIKEY"), self.api_key)

        asyncio.run(run_test())

    def test_ws_authenticate_async(self):
        """Test WebSocket authentication (async)."""
        async def run_test():
            request = WSRequest(payload={})

            authenticated_request = await self.auth.ws_authenticate(request)

            self.assertIsNotNone(authenticated_request)
            # WebSocket auth is pass-through for now
            self.assertEqual(authenticated_request, request)

        asyncio.run(run_test())

    def test_header_for_authentication(self):
        """Test authentication headers."""
        headers = self.auth.header_for_authentication()

        self.assertIn("X-COINS-APIKEY", headers)
        self.assertEqual(headers["X-COINS-APIKEY"], self.api_key)
        self.assertIn("User-Agent", headers)
        self.assertIn("Content-Type", headers)

    def test_is_timestamp_valid(self):
        """Test timestamp validation."""
        current_time = int(time.time() * 1000)

        # Valid timestamp (within 5 minutes)
        valid_timestamp = current_time - 60000  # 1 minute ago
        self.assertTrue(self.auth.is_timestamp_valid(valid_timestamp))

        # Invalid timestamp (too old)
        invalid_timestamp = current_time - 400000  # Over 6 minutes ago
        self.assertFalse(self.auth.is_timestamp_valid(invalid_timestamp))

    def test_signature_with_empty_params(self):
        """Test signature generation with empty parameters."""
        params = {}
        signature = self.auth._generate_signature(params)
        self.assertIsInstance(signature, str)
        self.assertTrue(len(signature) > 0)

    def test_signature_with_special_characters(self):
        """Test signature generation with special characters."""
        params = {"symbol": "BTC/USDT", "side": "BUY&SELL"}
        signature = self.auth._generate_signature(params)
        self.assertIsInstance(signature, str)
        self.assertTrue(len(signature) > 0)

    def test_validate_credentials(self):
        """Test credential validation."""
        # Valid credentials
        self.assertTrue(self.auth.validate_credentials())

        # Invalid credentials
        invalid_auth = CoinsxyzAuth("", "")
        self.assertFalse(invalid_auth.validate_credentials())

        # None credentials
        none_auth = CoinsxyzAuth(None, None)
        self.assertFalse(none_auth.validate_credentials())

    def test_get_timestamp(self):
        """Test timestamp generation."""
        timestamp = self.auth.get_timestamp()

        self.assertIsInstance(timestamp, int)
        self.assertGreater(timestamp, 0)

        # Should be close to current time
        current_time = int(time.time() * 1000)
        self.assertLess(abs(timestamp - current_time), 5000)  # Within 5 seconds

    def test_validate_timestamp(self):
        """Test timestamp validation with custom tolerance."""
        current_time = int(time.time() * 1000)

        # Valid with default tolerance
        self.assertTrue(self.auth.validate_timestamp(current_time - 30000))  # 30s ago

        # Invalid with default tolerance
        self.assertFalse(self.auth.validate_timestamp(current_time - 120000))  # 2min ago

        # Valid with custom tolerance
        self.assertTrue(self.auth.validate_timestamp(current_time - 120000, 180000))  # 3min tolerance

    def test_get_auth_headers(self):
        """Test authentication headers generation."""
        headers = self.auth.get_auth_headers("GET", "/test", {"symbol": "BTCUSDT"})

        self.assertIn("X-COINS-APIKEY", headers)
        self.assertIn("X-COINS-TIMESTAMP", headers)
        self.assertIn("X-COINS-SIGNATURE", headers)
        self.assertEqual(headers["X-COINS-APIKEY"], self.api_key)

    def test_add_auth_to_params(self):
        """Test adding authentication to parameters."""
        params = {"symbol": "BTCUSDT", "side": "BUY"}
        auth_params = self.auth.add_auth_to_params(params)

        self.assertIn("timestamp", auth_params)
        self.assertIn("signature", auth_params)
        self.assertIn("symbol", auth_params)
        self.assertIn("side", auth_params)


class TestTimeSynchronizerFixed(unittest.TestCase):
    """Fixed unit tests for TimeSynchronizer."""

    def setUp(self):
        """Set up test fixtures."""
        self.time_sync = TimeSynchronizer()

    def test_init(self):
        """Test time synchronizer initialization."""
        self.assertIsNotNone(self.time_sync)

    def test_time(self):
        """Test timestamp generation."""
        timestamp = self.time_sync.time()

        self.assertIsInstance(timestamp, float)
        self.assertGreater(timestamp, 0)

        # Should be close to current time
        current_time = time.time()
        self.assertLess(abs(timestamp - current_time), 1.0)  # Within 1 second

    def test_time_offset_ms(self):
        """Test time offset calculation."""
        offset = self.time_sync.time_offset_ms

        self.assertIsInstance(offset, (int, float))

    def test_timestamp_consistency(self):
        """Test timestamp consistency over short periods."""
        timestamp1 = self.time_sync.time()
        timestamp2 = self.time_sync.time()

        # Timestamps should be very close (within 0.1s)
        self.assertLess(abs(timestamp2 - timestamp1), 0.1)


if __name__ == "__main__":
    unittest.main()
