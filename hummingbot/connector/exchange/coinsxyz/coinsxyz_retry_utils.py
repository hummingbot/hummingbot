"""
Retry utilities for Coins.xyz Exchange Connector

This module provides retry logic and error handling utilities for API requests.
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict


class RetryType(Enum):
    """Types of retry strategies."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    FIXED_DELAY = "fixed_delay"
    LINEAR_BACKOFF = "linear_backoff"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    retry_type: RetryType = RetryType.EXPONENTIAL_BACKOFF
    retry_on_exceptions: tuple = (Exception,)


class RetryConfigs:
    """Predefined retry configurations."""

    STANDARD = RetryConfig(
        max_attempts=3,
        initial_delay=1.0,
        max_delay=30.0,
        backoff_multiplier=2.0
    )

    AGGRESSIVE = RetryConfig(
        max_attempts=5,
        initial_delay=0.5,
        max_delay=60.0,
        backoff_multiplier=2.0
    )

    CONSERVATIVE = RetryConfig(
        max_attempts=2,
        initial_delay=2.0,
        max_delay=10.0,
        backoff_multiplier=1.5
    )


class CoinsxyzRetryHandler:
    """Retry handler for Coins.xyz API requests."""

    def __init__(self, config: RetryConfig = None):
        """Initialize retry handler with configuration."""
        self._config = config or RetryConfigs.STANDARD
        self.config = self._config  # Alias for backward compatibility
        self.logger = logging.getLogger(__name__)
        self._retry_count = 0
        self._retry_stats = {}

    async def execute_with_retry(self,
                                 func: Callable,
                                 *args,
                                 **kwargs) -> Any:
        """Execute function with retry logic."""
        last_exception = None

        for attempt in range(self.config.max_attempts):
            try:
                self._retry_count = attempt
                return await func(*args, **kwargs)
            except self.config.retry_on_exceptions as e:
                last_exception = e

                if attempt == self.config.max_attempts - 1:
                    # Last attempt, don't retry
                    break

                delay = self._calculate_delay(attempt)
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s")
                await asyncio.sleep(delay)

        # All attempts failed
        raise last_exception

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt."""
        if self.config.retry_type == RetryType.EXPONENTIAL_BACKOFF:
            delay = self.config.initial_delay * (self.config.backoff_multiplier ** attempt)
        elif self.config.retry_type == RetryType.LINEAR_BACKOFF:
            delay = self.config.initial_delay * (attempt + 1)
        else:  # FIXED_DELAY
            delay = self.config.initial_delay

        return min(delay, self.config.max_delay)

    def calculate_backoff_delay(self, attempt: int) -> float:
        """
        Calculate backoff delay for retry attempt.

        Args:
            attempt: Attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        return self._calculate_delay(attempt)

    def handle_rate_limit(self, headers: Dict[str, str]) -> float:
        """
        Handle rate limit response.

        Args:
            headers: Response headers

        Returns:
            Delay in seconds
        """
        # Check for Retry-After header
        retry_after = headers.get("Retry-After", headers.get("retry-after"))
        
        if retry_after:
            try:
                return float(retry_after)
            except (ValueError, TypeError):
                pass
        
        # Default rate limit delay
        return 60.0

    def reset_retry_count(self):
        """Reset retry counter."""
        self._retry_count = 0

    def should_retry_request(self, error: Exception, attempt: int) -> bool:
        """
        Determine if request should be retried.

        Args:
            error: Exception that occurred
            attempt: Current attempt number

        Returns:
            True if should retry, False otherwise
        """
        # Check if we've exceeded max attempts
        if attempt >= self.config.max_attempts:
            return False

        # Check if error is retryable
        if not isinstance(error, self.config.retry_on_exceptions):
            return False

        # Check if error is in retryable list
        return is_retryable_error(error)

    def handle_network_failure(self, error: Exception) -> float:
        """
        Handle network failure.

        Args:
            error: Network error

        Returns:
            Delay before retry in seconds
        """
        self.logger.warning(f"Network failure: {error}")
        return self.config.initial_delay

    def recover_connection(self) -> bool:
        """
        Attempt to recover connection.

        Returns:
            True if recovery successful
        """
        # Reset retry count on recovery
        self.reset_retry_count()
        return True


def retry_on_rate_limit(func: Callable) -> Callable:
    """Decorator for retrying on rate limit errors."""
    async def wrapper(*args, **kwargs):
        retry_handler = CoinsxyzRetryHandler(RetryConfigs.CONSERVATIVE)
        return await retry_handler.execute_with_retry(func, *args, **kwargs)

    return wrapper


def is_retryable_error(error: Exception) -> bool:
    """Check if an error is retryable."""
    error_str = str(error).lower()

    retryable_indicators = [
        "timeout",
        "connection",
        "network",
        "503",  # Service Unavailable
        "502",  # Bad Gateway
        "504",  # Gateway Timeout
        "429",  # Too Many Requests
    ]

    return any(indicator in error_str for indicator in retryable_indicators)
