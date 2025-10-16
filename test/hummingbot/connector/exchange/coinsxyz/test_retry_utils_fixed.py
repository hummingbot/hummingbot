#!/usr/bin/env python3
"""
Fixed Unit Tests for Coins.xyz Retry Utils
"""

import asyncio
import unittest

from hummingbot.connector.exchange.coinsxyz.coinsxyz_retry_utils import (
    CoinsxyzRetryHandler,
    RetryConfig,
    RetryConfigs,
    RetryType,
    is_retryable_error,
    retry_on_rate_limit,
)


class TestCoinsxyzRetryHandlerFixed(unittest.TestCase):
    """Fixed unit tests for CoinsxyzRetryHandler."""

    def setUp(self):
        """Set up test fixtures."""
        self.retry_handler = CoinsxyzRetryHandler(RetryConfigs.STANDARD)

    def test_init(self):
        """Test retry handler initialization."""
        self.assertIsNotNone(self.retry_handler.config)
        self.assertEqual(self.retry_handler.config.max_attempts, 3)

    def test_calculate_delay_exponential(self):
        """Test exponential backoff delay calculation."""
        config = RetryConfig(
            initial_delay=1.0,
            backoff_multiplier=2.0,
            max_delay=30.0,
            retry_type=RetryType.EXPONENTIAL_BACKOFF
        )
        handler = CoinsxyzRetryHandler(config)

        delay1 = handler._calculate_delay(0)
        delay2 = handler._calculate_delay(1)
        delay3 = handler._calculate_delay(2)

        self.assertEqual(delay1, 1.0)
        self.assertEqual(delay2, 2.0)
        self.assertEqual(delay3, 4.0)

    def test_calculate_delay_linear(self):
        """Test linear backoff delay calculation."""
        config = RetryConfig(
            initial_delay=1.0,
            retry_type=RetryType.LINEAR_BACKOFF
        )
        handler = CoinsxyzRetryHandler(config)

        delay1 = handler._calculate_delay(0)
        delay2 = handler._calculate_delay(1)
        delay3 = handler._calculate_delay(2)

        self.assertEqual(delay1, 1.0)
        self.assertEqual(delay2, 2.0)
        self.assertEqual(delay3, 3.0)

    def test_calculate_delay_fixed(self):
        """Test fixed delay calculation."""
        config = RetryConfig(
            initial_delay=5.0,
            retry_type=RetryType.FIXED_DELAY
        )
        handler = CoinsxyzRetryHandler(config)

        delay1 = handler._calculate_delay(0)
        delay2 = handler._calculate_delay(1)
        delay3 = handler._calculate_delay(2)

        self.assertEqual(delay1, 5.0)
        self.assertEqual(delay2, 5.0)
        self.assertEqual(delay3, 5.0)

    def test_calculate_delay_max_limit(self):
        """Test delay max limit enforcement."""
        config = RetryConfig(
            initial_delay=10.0,
            backoff_multiplier=3.0,
            max_delay=20.0,
            retry_type=RetryType.EXPONENTIAL_BACKOFF
        )
        handler = CoinsxyzRetryHandler(config)

        delay = handler._calculate_delay(5)  # Would be 10 * 3^5 = 2430
        self.assertEqual(delay, 20.0)  # Should be capped at max_delay

    def test_execute_with_retry_success(self):
        """Test successful execution without retry."""
        async def run_test():
            async def success_func():
                return "success"

            result = await self.retry_handler.execute_with_retry(success_func)
            self.assertEqual(result, "success")

        asyncio.run(run_test())

    def test_execute_with_retry_failure(self):
        """Test execution with retries and eventual failure."""
        async def run_test():
            call_count = 0

            async def failing_func():
                nonlocal call_count
                call_count += 1
                raise ValueError("Test error")

            with self.assertRaises(ValueError):
                await self.retry_handler.execute_with_retry(failing_func)

            self.assertEqual(call_count, 3)  # Should retry max_attempts times

        asyncio.run(run_test())

    def test_execute_with_retry_eventual_success(self):
        """Test execution that succeeds after retries."""
        async def run_test():
            call_count = 0

            async def eventually_success_func():
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise ValueError("Temporary error")
                return "success"

            result = await self.retry_handler.execute_with_retry(eventually_success_func)
            self.assertEqual(result, "success")
            self.assertEqual(call_count, 3)

        asyncio.run(run_test())

    def test_retry_configs(self):
        """Test predefined retry configurations."""
        # Standard config
        self.assertEqual(RetryConfigs.STANDARD.max_attempts, 3)
        self.assertEqual(RetryConfigs.STANDARD.initial_delay, 1.0)

        # Aggressive config
        self.assertEqual(RetryConfigs.AGGRESSIVE.max_attempts, 5)
        self.assertEqual(RetryConfigs.AGGRESSIVE.initial_delay, 0.5)

        # Conservative config
        self.assertEqual(RetryConfigs.CONSERVATIVE.max_attempts, 2)
        self.assertEqual(RetryConfigs.CONSERVATIVE.initial_delay, 2.0)


class TestRetryUtilityFunctions(unittest.TestCase):
    """Test utility functions for retry logic."""

    def test_is_retryable_error(self):
        """Test retryable error detection."""
        # Retryable errors
        self.assertTrue(is_retryable_error(Exception("Connection timeout")))
        self.assertTrue(is_retryable_error(Exception("Network error")))
        self.assertTrue(is_retryable_error(Exception("503 Service Unavailable")))
        self.assertTrue(is_retryable_error(Exception("429 Too Many Requests")))

        # Non-retryable errors
        self.assertFalse(is_retryable_error(Exception("Invalid API key")))
        self.assertFalse(is_retryable_error(Exception("Bad request")))

    def test_retry_on_rate_limit_decorator(self):
        """Test rate limit retry decorator."""
        async def run_test():
            call_count = 0

            @retry_on_rate_limit
            async def rate_limited_func():
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    raise Exception("429 Too Many Requests")
                return "success"

            result = await rate_limited_func()
            self.assertEqual(result, "success")
            self.assertEqual(call_count, 2)

        asyncio.run(run_test())


class TestRetryConfig(unittest.TestCase):
    """Test RetryConfig dataclass."""

    def test_retry_config_defaults(self):
        """Test default retry configuration values."""
        config = RetryConfig()

        self.assertEqual(config.max_attempts, 3)
        self.assertEqual(config.initial_delay, 1.0)
        self.assertEqual(config.max_delay, 60.0)
        self.assertEqual(config.backoff_multiplier, 2.0)
        self.assertEqual(config.retry_type, RetryType.EXPONENTIAL_BACKOFF)
        self.assertEqual(config.retry_on_exceptions, (Exception,))

    def test_retry_config_custom(self):
        """Test custom retry configuration."""
        config = RetryConfig(
            max_attempts=5,
            initial_delay=0.5,
            max_delay=30.0,
            backoff_multiplier=1.5,
            retry_type=RetryType.LINEAR_BACKOFF,
            retry_on_exceptions=(ValueError, ConnectionError)
        )

        self.assertEqual(config.max_attempts, 5)
        self.assertEqual(config.initial_delay, 0.5)
        self.assertEqual(config.max_delay, 30.0)
        self.assertEqual(config.backoff_multiplier, 1.5)
        self.assertEqual(config.retry_type, RetryType.LINEAR_BACKOFF)
        self.assertEqual(config.retry_on_exceptions, (ValueError, ConnectionError))


class TestRetryType(unittest.TestCase):
    """Test RetryType enum."""

    def test_retry_type_values(self):
        """Test retry type enum values."""
        self.assertEqual(RetryType.EXPONENTIAL_BACKOFF.value, "exponential_backoff")
        self.assertEqual(RetryType.FIXED_DELAY.value, "fixed_delay")
        self.assertEqual(RetryType.LINEAR_BACKOFF.value, "linear_backoff")


if __name__ == "__main__":
    unittest.main()
