#!/usr/bin/env python3

import unittest

from hummingbot.connector.exchange.coinsxyz.coinsxyz_retry_utils import CoinsxyzRetryHandler, RetryConfigs


class TestCoinsxyzRetryHandler(unittest.TestCase):
    """Unit tests for CoinsxyzRetryHandler."""

    def setUp(self):
        """Set up test fixtures."""
        self.retry_handler = CoinsxyzRetryHandler(RetryConfigs.STANDARD)

    def test_init(self):
        """Test retry handler initialization."""
        self.assertIsNotNone(self.retry_handler)

    def test_calculate_backoff_delay(self):
        """Test exponential backoff calculation."""
        delay1 = self.retry_handler.calculate_backoff_delay(1)
        delay2 = self.retry_handler.calculate_backoff_delay(2)
        delay3 = self.retry_handler.calculate_backoff_delay(3)

        # Exponential backoff should increase delays
        self.assertGreater(delay2, delay1)
        self.assertGreater(delay3, delay2)
        self.assertIsInstance(delay1, (int, float))

    def test_should_retry_request(self):
        """Test retry decision logic."""
        # Test with generic exception
        error = Exception("Network error")

        # Should retry on first few attempts
        self.assertTrue(self.retry_handler.should_retry_request(error, 1))
        self.assertTrue(self.retry_handler.should_retry_request(error, 2))

        # Should not retry after max attempts
        self.assertFalse(self.retry_handler.should_retry_request(error, 10))

    def test_handle_rate_limit(self):
        """Test rate limit handling."""
        headers_with_retry = {"Retry-After": "30"}
        delay = self.retry_handler.handle_rate_limit(headers_with_retry)
        self.assertEqual(delay, 30.0)

        headers_without_retry = {}
        delay = self.retry_handler.handle_rate_limit(headers_without_retry)
        self.assertGreater(delay, 0)

    def test_reset_retry_count(self):
        """Test retry count reset."""
        self.retry_handler.reset_retry_count()
        # Should not raise any exceptions
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
