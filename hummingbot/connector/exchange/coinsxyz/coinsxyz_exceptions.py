"""
Exception Classes and Error Mapping for Coins.xyz Exchange Connector

This module defines custom exception classes and provides comprehensive
error parsing and mapping functionality for the Coins.xyz API.
"""

import logging
from typing import Any, Dict, Optional


class CoinsxyzAPIError(Exception):
    """
    Base exception class for all Coins.xyz API errors.

    This is the parent class for all Coins.xyz-specific exceptions,
    providing common functionality for error handling and logging.
    """

    def __init__(self,
                 message: str,
                 error_code: Optional[int] = None,
                 status_code: Optional[int] = None,
                 response_data: Optional[Dict[str, Any]] = None):
        """
        Initialize CoinsxyzAPIError.

        :param message: Human-readable error message
        :param error_code: Coins.ph API error code (negative values)
        :param status_code: HTTP status code
        :param response_data: Full response data from API
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.response_data = response_data or {}

        # Log the error for debugging
        logger = logging.getLogger(__name__)
        logger.debug(f"CoinsxyzAPIError: {message} (code: {error_code}, status: {status_code})")

    def __str__(self) -> str:
        """String representation of the error."""
        if self.error_code:
            return f"Coins.ph API Error {self.error_code}: {self.message}"
        return f"Coins.ph API Error: {self.message}"

    def __repr__(self) -> str:
        """Detailed representation of the error."""
        return (f"CoinsxyzAPIError(message='{self.message}', "
                f"error_code={self.error_code}, status_code={self.status_code})")


class CoinsxyzRateLimitError(CoinsxyzAPIError):
    """
    Exception raised when API rate limits are exceeded.

    This exception is raised when the API returns rate limiting errors,
    indicating that too many requests have been made in a short period.
    """

    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        """
        Initialize CoinsxyzRateLimitError.

        :param message: Error message
        :param retry_after: Seconds to wait before retrying
        :param kwargs: Additional arguments passed to parent
        """
        super().__init__(message, **kwargs)
        self.retry_after = retry_after

    def __str__(self) -> str:
        base_msg = super().__str__()
        if self.retry_after:
            return f"{base_msg} (retry after {self.retry_after}s)"
        return base_msg


class CoinsxyzAuthenticationError(CoinsxyzAPIError):
    """
    Exception raised for authentication-related errors.

    This includes invalid API keys, signature errors, timestamp issues,
    and other authentication failures.
    """

    def __init__(self, message: str, **kwargs):
        """
        Initialize CoinsxyzAuthenticationError.

        :param message: Error message
        :param kwargs: Additional arguments passed to parent
        """
        super().__init__(message, **kwargs)


class CoinsxyzPermissionError(CoinsxyzAPIError):
    """
    Exception raised when API permissions are insufficient.

    This occurs when the API key doesn't have the required permissions
    for the requested operation.
    """

    def __init__(self, message: str, required_permission: Optional[str] = None, **kwargs):
        """
        Initialize CoinsxyzPermissionError.

        :param message: Error message
        :param required_permission: The permission that is required
        :param kwargs: Additional arguments passed to parent
        """
        super().__init__(message, **kwargs)
        self.required_permission = required_permission


class CoinsxyzOrderError(CoinsxyzAPIError):
    """
    Exception raised for order-related errors.

    This includes invalid order parameters, insufficient balance,
    order not found, and other order-specific errors.
    """

    def __init__(self, message: str, order_id: Optional[str] = None, **kwargs):
        """
        Initialize CoinsxyzOrderError.

        :param message: Error message
        :param order_id: The order ID related to the error
        :param kwargs: Additional arguments passed to parent
        """
        super().__init__(message, **kwargs)
        self.order_id = order_id

    def __str__(self) -> str:
        """String representation of the error."""
        return self.message


class CoinsxyzMarketError(CoinsxyzAPIError):
    """
    Exception raised for market-related errors.

    This includes invalid trading pairs, market not found,
    trading suspended, and other market-specific errors.
    """

    def __init__(self, message: str, trading_pair: Optional[str] = None, **kwargs):
        """
        Initialize CoinsxyzMarketError.

        :param message: Error message
        :param trading_pair: The trading pair related to the error
        :param kwargs: Additional arguments passed to parent
        """
        super().__init__(message, **kwargs)
        self.trading_pair = trading_pair


class CoinsxyzServerError(CoinsxyzAPIError):
    """
    Exception raised for server-side errors.

    This includes internal server errors, service unavailable,
    and other server-related issues.
    """

    def __init__(self, message: str, **kwargs):
        """
        Initialize CoinsxyzServerError.

        :param message: Error message
        :param kwargs: Additional arguments passed to parent
        """
        super().__init__(message, **kwargs)


class CoinsxyzClientError(CoinsxyzAPIError):
    """
    Exception raised for client-side errors.

    This includes bad requests, invalid parameters,
    and other client-related issues.
    """

    def __init__(self, message: str, **kwargs):
        """
        Initialize CoinsxyzClientError.

        :param message: Error message
        :param kwargs: Additional arguments passed to parent
        """
        super().__init__(message, **kwargs)


class CoinsxyzNetworkError(CoinsxyzAPIError):
    """
    Exception raised for network-related errors.

    This includes connection timeouts, DNS resolution failures,
    and other network connectivity issues.
    """

    def __init__(self, message: str, **kwargs):
        """
        Initialize CoinsxyzNetworkError.

        :param message: Error message
        :param kwargs: Additional arguments passed to parent
        """
        super().__init__(message, **kwargs)

    def __str__(self) -> str:
        """String representation of the error."""
        return self.message


class CoinsxyzErrorParser:
    """
    Parser for Coins.ph API errors with comprehensive error mapping.

    This class provides methods to parse API error responses and map them
    to appropriate exception classes based on error codes and HTTP status codes.
    """

    # Error code mappings based on Coins.ph API documentation
    ERROR_CODE_MAPPINGS = {
        # Rate limiting errors
        -1003: CoinsxyzRateLimitError,
        -1015: CoinsxyzRateLimitError,

        # Authentication errors
        -1022: CoinsxyzAuthenticationError,  # Invalid signature
        -2014: CoinsxyzAuthenticationError,  # API key format invalid
        -2015: CoinsxyzAuthenticationError,  # Invalid API key, IP, or permissions
        -2016: CoinsxyzAuthenticationError,  # No trading window could be found
        -2018: CoinsxyzAuthenticationError,  # API key does not exist
        -2019: CoinsxyzAuthenticationError,  # API key is disabled

        # Order errors
        -1013: CoinsxyzOrderError,           # Invalid quantity
        -1020: CoinsxyzOrderError,           # Unsupported operation
        -2011: CoinsxyzOrderError,           # Order cancel rejected
        -2013: CoinsxyzOrderError,           # Order does not exist
        -2021: CoinsxyzOrderError,           # Order would immediately trigger

        # Permission errors (insufficient balance, etc.)
        -2010: CoinsxyzPermissionError,      # Account has insufficient balance / New order rejected

        # Market errors
        -1100: CoinsxyzMarketError,          # Illegal characters found in a parameter
        -1101: CoinsxyzMarketError,          # Too many parameters sent
        -1102: CoinsxyzMarketError,          # Mandatory parameter was not sent
        -1121: CoinsxyzMarketError,          # Invalid symbol
        -100011: CoinsxyzMarketError,        # Not supported symbols

        # Client errors (general)
        -1000: CoinsxyzClientError,          # Unknown error occurred
        -1001: CoinsxyzClientError,          # Internal error; unable to process your request
        -1002: CoinsxyzClientError,          # You are not authorized to execute this request
        -1006: CoinsxyzClientError,          # Unexpected response received from message bus
        -1007: CoinsxyzClientError,          # Timeout waiting for response from backend server

        # Server errors
        -1008: CoinsxyzServerError,          # Server is currently overloaded
        -1014: CoinsxyzServerError,          # Unsupported order combination
        -1016: CoinsxyzServerError,          # Service shutting down or unavailable
    }

    # HTTP status code mappings
    HTTP_STATUS_MAPPINGS = {
        400: CoinsxyzClientError,
        401: CoinsxyzAuthenticationError,
        403: CoinsxyzPermissionError,
        404: CoinsxyzClientError,
        429: CoinsxyzRateLimitError,
        500: CoinsxyzServerError,
        502: CoinsxyzServerError,
        503: CoinsxyzServerError,
        504: CoinsxyzServerError,
    }

    @classmethod
    def parse_error(cls,
                    status_code: int,
                    response_data: Dict[str, Any],
                    default_message: str = "Unknown API error") -> CoinsxyzAPIError:
        """
        Parse an API error response and return the appropriate exception.

        :param status_code: HTTP status code
        :param response_data: Response data from API
        :param default_message: Default message if none found in response
        :return: Appropriate CoinsxyzAPIError subclass instance
        """
        # Extract error information from response
        error_code = response_data.get("code")
        error_message = response_data.get("msg", default_message)

        # Create full error message
        if error_code:
            full_message = f"Coins.ph API Error {error_code}: {error_message}"
        else:
            full_message = f"Coins.ph API Error: {error_message}"

        # Determine exception class based on error code first
        exception_class = CoinsxyzAPIError

        if error_code and error_code in cls.ERROR_CODE_MAPPINGS:
            exception_class = cls.ERROR_CODE_MAPPINGS[error_code]
        elif status_code in cls.HTTP_STATUS_MAPPINGS:
            exception_class = cls.HTTP_STATUS_MAPPINGS[status_code]

        # Handle special cases
        kwargs = {
            "message": full_message,
            "error_code": error_code,
            "status_code": status_code,
            "response_data": response_data
        }

        # Add specific parameters for certain exception types
        if exception_class == CoinsxyzRateLimitError:
            # Try to extract retry-after information
            retry_after = cls._extract_retry_after(response_data, status_code)
            if retry_after:
                kwargs["retry_after"] = retry_after

        return exception_class(**kwargs)

    @classmethod
    def _extract_retry_after(cls, response_data: Dict[str, Any], status_code: int) -> Optional[int]:
        """
        Extract retry-after information from rate limit error.

        :param response_data: Response data from API
        :param status_code: HTTP status code
        :return: Seconds to wait before retrying, or None
        """
        # Check for retry-after header information in response
        if "retryAfter" in response_data:
            try:
                return int(response_data["retryAfter"])
            except (ValueError, TypeError):
                pass

        # Default retry times based on error patterns
        if status_code == 429:
            return 60  # Default 1 minute for rate limiting

        return None

    @classmethod
    def is_retryable_error(cls, error: CoinsxyzAPIError) -> bool:
        """
        Determine if an error is retryable.

        :param error: The error to check
        :return: True if the error is retryable
        """
        # Rate limit errors are retryable
        if isinstance(error, CoinsxyzRateLimitError):
            return True

        # Server errors are generally retryable
        if isinstance(error, CoinsxyzServerError):
            return True

        # Network errors are retryable
        if isinstance(error, CoinsxyzNetworkError):
            return True

        # Specific error codes that are retryable
        retryable_codes = {
            -1006,  # Unexpected response from message bus
            -1007,  # Timeout waiting for backend server
            -1008,  # Server overloaded
        }

        if error.error_code in retryable_codes:
            return True

        return False

    @classmethod
    def get_retry_delay(cls, error: CoinsxyzAPIError, attempt: int = 1) -> int:
        """
        Get the recommended retry delay for an error.

        :param error: The error that occurred
        :param attempt: The retry attempt number (1-based)
        :return: Seconds to wait before retrying
        """
        # Use explicit retry-after if available
        if isinstance(error, CoinsxyzRateLimitError) and error.retry_after:
            return error.retry_after

        # Exponential backoff for retryable errors
        if cls.is_retryable_error(error):
            base_delay = 1
            max_delay = 300  # 5 minutes max

            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            return delay

        return 0  # No retry for non-retryable errors
