#!/usr/bin/env python3
"""
Unit Tests for Coins.xyz Exceptions
"""

import unittest

from hummingbot.connector.exchange.coinsxyz.coinsxyz_exceptions import (
    CoinsxyzAPIError,
    CoinsxyzAuthenticationError,
    CoinsxyzNetworkError,
    CoinsxyzOrderError,
    CoinsxyzRateLimitError,
)


class TestCoinsxyzExceptions(unittest.TestCase):
    """Unit tests for Coinsxyz exceptions."""

    def test_api_error(self):
        """Test CoinsxyzAPIError."""
        error = CoinsxyzAPIError("API Error", error_code=-1121)

        self.assertEqual(str(error), "API Error")
        self.assertEqual(error.error_code, -1121)
        self.assertIsInstance(error, Exception)

    def test_network_error(self):
        """Test CoinsxyzNetworkError."""
        error = CoinsxyzNetworkError("Network timeout")

        self.assertEqual(str(error), "Network timeout")
        self.assertIsInstance(error, CoinsxyzAPIError)

    def test_order_error(self):
        """Test CoinsxyzOrderError."""
        error = CoinsxyzOrderError("Invalid order", order_id="12345")

        self.assertEqual(str(error), "Invalid order")
        self.assertEqual(error.order_id, "12345")
        self.assertIsInstance(error, CoinsxyzAPIError)

    def test_auth_error(self):
        """Test CoinsxyzAuthenticationError."""
        error = CoinsxyzAuthenticationError("Invalid signature")

        self.assertEqual(str(error), "Coins.ph API Error: Invalid signature")
        self.assertIsInstance(error, CoinsxyzAPIError)

    def test_rate_limit_error(self):
        """Test CoinsxyzRateLimitError."""
        error = CoinsxyzRateLimitError("Rate limit exceeded", retry_after=60)

        self.assertEqual(str(error), "Rate limit exceeded")
        self.assertEqual(error.retry_after, 60)
        self.assertIsInstance(error, CoinsxyzAPIError)

    def test_error_from_response(self):
        """Test creating error from API response."""
        response = {
            "code": -1121,
            "msg": "Invalid symbol"
        }

        error = CoinsxyzAPIError.from_response(response)

        self.assertEqual(error.error_code, -1121)
        self.assertIn("Invalid symbol", str(error))

    def test_is_retryable_error(self):
        """Test retryable error detection."""
        # Network errors should be retryable
        network_error = CoinsxyzNetworkError("Connection failed")
        self.assertTrue(network_error.is_retryable())

        # Rate limit errors should be retryable
        rate_limit_error = CoinsxyzRateLimitError("Rate limit exceeded")
        self.assertTrue(rate_limit_error.is_retryable())

        # Auth errors should not be retryable
        auth_error = CoinsxyzAuthenticationError("Invalid API key")
        # Note: CoinsxyzAuthenticationError doesn't have is_retryable method, using parser
        from hummingbot.connector.exchange.coinsxyz.coinsxyz_exceptions import CoinsxyzErrorParser
        self.assertFalse(CoinsxyzErrorParser.is_retryable_error(auth_error))

        # Order errors should not be retryable
        order_error = CoinsxyzOrderError("Invalid order size")
        self.assertFalse(order_error.is_retryable())


if __name__ == "__main__":
    unittest.main()
