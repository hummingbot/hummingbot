"""
Retry utilities for Coins.xyz Exchange Connector

This module provides retry logic and error handling utilities for API requests.
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable


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
        self.config = config or RetryConfigs.STANDARD
        self.logger = logging.getLogger(__name__)

    async def execute_with_retry(self,
                                 func: Callable,
                                 *args,
                                 **kwargs) -> Any:
        """Execute function with retry logic."""
        last_exception = None

        for attempt in range(self.config.max_attempts):
            try:
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
