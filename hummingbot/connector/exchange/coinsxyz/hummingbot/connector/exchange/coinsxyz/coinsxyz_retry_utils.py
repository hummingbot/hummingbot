"""
Rate limit backoff and retry utilities for Coins.xyz API.

This module provides comprehensive retry logic with exponential backoff,
jitter, and intelligent rate limit handling for the Coins.xyz exchange connector.
"""

import asyncio
import logging
import random
import time
from typing import Any, Callable, Dict, Optional, Type, Union
from dataclasses import dataclass
from enum import Enum

from hummingbot.connector.exchange.coinsxyz.coinsxyz_exceptions import (
    CoinsxyzAPIError,
    CoinsxyzRateLimitError,
    CoinsxyzNetworkError,
    CoinsxyzServerError,
    CoinsxyzErrorParser
)


class RetryStrategy(Enum):
    """Retry strategy types."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    IMMEDIATE = "immediate"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 300.0  # 5 minutes
    backoff_multiplier: float = 2.0
    jitter: bool = True
    jitter_range: float = 0.1  # ±10% jitter
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    
    # Rate limit specific settings
    rate_limit_base_delay: float = 60.0  # 1 minute base delay for rate limits
    rate_limit_max_delay: float = 900.0  # 15 minutes max delay for rate limits
    
    # Retryable error types
    retryable_errors: tuple = (
        CoinsxyzRateLimitError,
        CoinsxyzNetworkError,
        CoinsxyzServerError
    )


class CoinsxyzRetryHandler:
    """
    Advanced retry handler with exponential backoff and rate limit awareness.
    
    This class provides intelligent retry logic for Coins.xyz API requests,
    including special handling for rate limit errors and network issues.
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        """
        Initialize the retry handler.
        
        :param config: Retry configuration, uses defaults if None
        """
        self.config = config or RetryConfig()
        self.logger = logging.getLogger(__name__)
        
        # Track retry statistics
        self._retry_stats = {
            "total_retries": 0,
            "rate_limit_retries": 0,
            "network_retries": 0,
            "server_error_retries": 0,
            "successful_retries": 0
        }
    
    async def execute_with_retry(self,
                                func: Callable,
                                *args,
                                **kwargs) -> Any:
        """
        Execute a function with retry logic.
        
        :param func: The async function to execute
        :param args: Positional arguments for the function
        :param kwargs: Keyword arguments for the function
        :return: Function result
        :raises: Final exception if all retries are exhausted
        """
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):  # +1 for initial attempt
            try:
                if attempt > 0:
                    self.logger.info(f"Retry attempt {attempt}/{self.config.max_retries}")
                
                result = await func(*args, **kwargs)
                
                if attempt > 0:
                    self._retry_stats["successful_retries"] += 1
                    self.logger.info(f"Request succeeded after {attempt} retries")
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Check if this is the last attempt
                if attempt >= self.config.max_retries:
                    self.logger.error(f"All retry attempts exhausted. Final error: {e}")
                    break
                
                # Check if error is retryable
                if not self._is_retryable_error(e):
                    self.logger.warning(f"Non-retryable error encountered: {e}")
                    break
                
                # Calculate delay and wait
                delay = self._calculate_delay(e, attempt + 1)
                
                self.logger.warning(
                    f"Request failed (attempt {attempt + 1}/{self.config.max_retries + 1}): {e}. "
                    f"Retrying in {delay:.2f}s"
                )
                
                # Update statistics
                self._update_retry_stats(e)
                
                await asyncio.sleep(delay)
        
        # All retries exhausted, raise the last exception
        raise last_exception
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """
        Check if an error is retryable.
        
        :param error: The error to check
        :return: True if the error should be retried
        """
        # Check if error type is in retryable list
        if isinstance(error, self.config.retryable_errors):
            return True
        
        # Special handling for HTTP status codes
        if hasattr(error, 'status_code'):
            status_code = error.status_code
            
            # Retryable HTTP status codes
            retryable_status_codes = {
                429,  # Too Many Requests
                500,  # Internal Server Error
                502,  # Bad Gateway
                503,  # Service Unavailable
                504,  # Gateway Timeout
                520,  # Unknown Error (Cloudflare)
                521,  # Web Server Is Down (Cloudflare)
                522,  # Connection Timed Out (Cloudflare)
                523,  # Origin Is Unreachable (Cloudflare)
                524,  # A Timeout Occurred (Cloudflare)
            }
            
            return status_code in retryable_status_codes
        
        # Check for specific error messages that indicate temporary issues
        error_message = str(error).lower()
        temporary_error_indicators = [
            "timeout",
            "connection",
            "network",
            "temporary",
            "unavailable",
            "overloaded"
        ]
        
        return any(indicator in error_message for indicator in temporary_error_indicators)
    
    def _calculate_delay(self, error: Exception, attempt: int) -> float:
        """
        Calculate the delay before the next retry attempt.
        
        :param error: The error that occurred
        :param attempt: The retry attempt number (1-based)
        :return: Delay in seconds
        """
        # Special handling for rate limit errors
        if isinstance(error, CoinsxyzRateLimitError):
            return self._calculate_rate_limit_delay(error, attempt)
        
        # Calculate base delay based on strategy
        if self.config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.config.base_delay * (self.config.backoff_multiplier ** (attempt - 1))
        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.config.base_delay * attempt
        elif self.config.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.config.base_delay
        else:  # IMMEDIATE
            delay = 0
        
        # Apply maximum delay limit
        delay = min(delay, self.config.max_delay)
        
        # Add jitter if enabled
        if self.config.jitter and delay > 0:
            jitter_amount = delay * self.config.jitter_range
            jitter = random.uniform(-jitter_amount, jitter_amount)
            delay = max(0, delay + jitter)
        
        return delay
    
    def _calculate_rate_limit_delay(self, error: CoinsxyzRateLimitError, attempt: int) -> float:
        """
        Calculate delay for rate limit errors.
        
        :param error: The rate limit error
        :param attempt: The retry attempt number
        :return: Delay in seconds
        """
        # Use explicit retry-after if provided by the API
        if hasattr(error, 'retry_after') and error.retry_after:
            base_delay = float(error.retry_after)
        else:
            # Use exponential backoff for rate limits
            base_delay = self.config.rate_limit_base_delay * (2 ** (attempt - 1))
        
        # Apply rate limit specific maximum
        delay = min(base_delay, self.config.rate_limit_max_delay)
        
        # Add jitter for rate limits to avoid thundering herd
        if self.config.jitter:
            jitter_amount = delay * 0.2  # 20% jitter for rate limits
            jitter = random.uniform(-jitter_amount, jitter_amount)
            delay = max(0, delay + jitter)
        
        return delay
    
    def _update_retry_stats(self, error: Exception):
        """
        Update retry statistics.
        
        :param error: The error that caused the retry
        """
        self._retry_stats["total_retries"] += 1
        
        if isinstance(error, CoinsxyzRateLimitError):
            self._retry_stats["rate_limit_retries"] += 1
        elif isinstance(error, CoinsxyzNetworkError):
            self._retry_stats["network_retries"] += 1
        elif isinstance(error, CoinsxyzServerError):
            self._retry_stats["server_error_retries"] += 1
    
    def get_retry_stats(self) -> Dict[str, int]:
        """
        Get retry statistics.
        
        :return: Dictionary of retry statistics
        """
        return self._retry_stats.copy()
    
    def reset_stats(self):
        """Reset retry statistics."""
        for key in self._retry_stats:
            self._retry_stats[key] = 0

    def handle_rate_limit(self, response_headers: Dict[str, str]) -> float:
        """
        Handle rate limit response and calculate backoff delay.

        Args:
            response_headers: HTTP response headers containing rate limit info

        Returns:
            Delay in seconds before next request
        """
        # Extract rate limit information from headers
        retry_after = response_headers.get('Retry-After')
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass

        # Use exponential backoff if no retry-after header
        return self._calculate_delay(1)

    def calculate_backoff_delay(self, attempt: int, base_delay: float = None) -> float:
        """
        Calculate backoff delay for a given attempt.

        Args:
            attempt: Current attempt number (1-based)
            base_delay: Base delay override

        Returns:
            Delay in seconds
        """
        if base_delay is None:
            base_delay = self._config.base_delay

        return self._calculate_delay(attempt, base_delay)

    def should_retry_request(self, exception: Exception, attempt: int) -> bool:
        """
        Determine if a request should be retried based on exception and attempt count.

        Args:
            exception: Exception that occurred
            attempt: Current attempt number

        Returns:
            True if request should be retried
        """
        if attempt >= self._config.max_retries:
            return False

        # Check if exception type is retryable
        return isinstance(exception, self._config.retryable_exceptions)

    def handle_network_failure(self, exception: Exception) -> float:
        """
        Handle network failure and return appropriate delay.

        Args:
            exception: Network exception that occurred

        Returns:
            Delay in seconds before retry
        """
        self._logger.warning(f"Network failure detected: {exception}")
        return self._config.base_delay * 2  # Double delay for network issues

    def retry_with_backoff(self, func: Callable, *args, **kwargs):
        """
        Retry function with exponential backoff.

        Args:
            func: Function to retry
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result or raises exception after max retries
        """
        return self.execute_with_retry(func, *args, **kwargs)

    def recover_connection(self) -> bool:
        """
        Attempt to recover connection after network failure.

        Returns:
            True if connection recovery successful
        """
        # This is a placeholder - actual implementation would depend on connection type
        self._logger.info("Attempting connection recovery")
        return True


# Predefined retry configurations for different scenarios
class RetryConfigs:
    """Predefined retry configurations for common scenarios."""
    
    # Conservative retry for critical operations
    CONSERVATIVE = RetryConfig(
        max_retries=2,
        base_delay=2.0,
        max_delay=60.0,
        backoff_multiplier=2.0,
        jitter=True
    )
    
    # Standard retry for normal operations
    STANDARD = RetryConfig(
        max_retries=3,
        base_delay=1.0,
        max_delay=300.0,
        backoff_multiplier=2.0,
        jitter=True
    )
    
    # Aggressive retry for non-critical operations
    AGGRESSIVE = RetryConfig(
        max_retries=5,
        base_delay=0.5,
        max_delay=600.0,
        backoff_multiplier=1.5,
        jitter=True
    )
    
    # Rate limit focused retry
    RATE_LIMIT_FOCUSED = RetryConfig(
        max_retries=3,
        base_delay=1.0,
        max_delay=300.0,
        rate_limit_base_delay=120.0,  # 2 minutes
        rate_limit_max_delay=1800.0,  # 30 minutes
        jitter=True
    )


# Convenience function for simple retry operations
async def retry_on_rate_limit(func: Callable, *args, **kwargs) -> Any:
    """
    Convenience function to retry a function with rate limit focused configuration.
    
    :param func: The async function to execute
    :param args: Positional arguments for the function
    :param kwargs: Keyword arguments for the function
    :return: Function result
    """
    handler = CoinsxyzRetryHandler(RetryConfigs.RATE_LIMIT_FOCUSED)
    return await handler.execute_with_retry(func, *args, **kwargs)


# Decorator for automatic retry
def with_retry(config: Optional[RetryConfig] = None):
    """
    Decorator to add retry logic to async functions.
    
    :param config: Retry configuration, uses standard if None
    :return: Decorated function
    """
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            handler = CoinsxyzRetryHandler(config or RetryConfigs.STANDARD)
            return await handler.execute_with_retry(func, *args, **kwargs)
        return wrapper
    return decorator


# Alias for backward compatibility and verification tests
CoinsxyzRetryUtils = CoinsxyzRetryHandler
