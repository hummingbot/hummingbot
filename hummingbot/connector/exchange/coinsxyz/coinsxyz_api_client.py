"""
REST API Client for Coins.xyz Exchange Connector

This module implements the REST API client with proper error handling,
request/response structure, and comprehensive logging for the Coins.xyz exchange.
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import aiohttp
from aiohttp import ClientTimeout

from hummingbot.connector.exchange.coinsxyz import coinsxyz_constants as CONSTANTS
from hummingbot.connector.exchange.coinsxyz.coinsxyz_auth import CoinsxyzAuth
from hummingbot.connector.exchange.coinsxyz.coinsxyz_exceptions import (
    CoinsxyzAPIError,
    CoinsxyzAuthenticationError,
    CoinsxyzClientError,
    CoinsxyzErrorParser,
    CoinsxyzNetworkError,
    CoinsxyzRateLimitError,
    CoinsxyzServerError,
)
from hummingbot.connector.exchange.coinsxyz.coinsxyz_logger import CoinsxyzRequestLogger, CoinsxyzDebugLogger
from hummingbot.connector.exchange.coinsxyz.coinsxyz_retry_utils import (
    CoinsxyzRetryHandler,
    RetryConfig,
    RetryConfigs
)
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.connections.data_types import RESTMethod


class CoinsxyzAPIClient:
    """
    REST API client for Coins.xyz exchange.

    Provides a clean interface for making authenticated and unauthenticated
    requests to the Coins.xyz API with proper error handling and logging.
    """

    def __init__(self,
                 auth: Optional[CoinsxyzAuth] = None,
                 throttler: Optional[AsyncThrottler] = None,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 timeout: float = 30.0,
                 retry_config: Optional[RetryConfig] = None):
        """
        Initialize the API client.

        :param auth: Authentication handler for private endpoints
        :param throttler: Rate limiter for API requests
        :param domain: API domain to use
        :param timeout: Request timeout in seconds
        :param retry_config: Retry configuration for failed requests
        """
        self._auth = auth
        self._throttler = throttler
        self._domain = domain
        self._timeout = ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None
        self._logger = logging.getLogger(__name__)

        # Initialize retry handler
        self._retry_handler = CoinsxyzRetryHandler(retry_config or RetryConfigs.STANDARD)

        # Initialize logging components
        self._request_logger = CoinsxyzRequestLogger(f"{__name__}.requests")
        self._debug_logger = CoinsxyzDebugLogger(f"{__name__}.debug")

        # Base URLs
        self._base_url = CONSTANTS.REST_URL

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def _ensure_session(self):
        """Ensure HTTP session is created."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=self._timeout,
                headers={
                    "User-Agent": "Hummingbot/CoinsphConnector",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
            )

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _build_url(self, endpoint: str, is_private: bool = False) -> str:
        """
        Build complete URL for an API endpoint.

        :param endpoint: API endpoint path
        :param is_private: Whether this is a private endpoint
        :return: Complete URL
        """
        api_version = CONSTANTS.PRIVATE_API_VERSION if is_private else CONSTANTS.PUBLIC_API_VERSION
        return urljoin(self._base_url, f"{api_version}{endpoint}")

    def _parse_error_response(self, status_code: int, response_data: Dict[str, Any]) -> CoinsxyzAPIError:
        """
        Parse error response and create appropriate exception.

        :param status_code: HTTP status code
        :param response_data: Response data from API
        :return: Appropriate exception instance
        """
        return CoinsxyzErrorParser.parse_error(status_code, response_data)

    async def request_with_retry(self,
                                 method: RESTMethod,
                                 endpoint: str,
                                 params: Optional[Dict[str, Any]] = None,
                                 data: Optional[Dict[str, Any]] = None,
                                 is_private: bool = False,
                                 rate_limit_id: Optional[str] = None,
                                 retry_config: Optional[RetryConfig] = None) -> Dict[str, Any]:
        """
        Make an API request with automatic retry logic.

        :param method: HTTP method (GET, POST, DELETE, etc.)
        :param endpoint: API endpoint path
        :param params: Query parameters
        :param data: Request body data
        :param is_private: Whether this is a private endpoint requiring authentication
        :param rate_limit_id: Rate limit identifier for throttling
        :param retry_config: Custom retry configuration for this request
        :return: API response as dictionary
        """
        # Use custom retry handler if provided, otherwise use instance handler
        if retry_config:
            retry_handler = CoinsxyzRetryHandler(retry_config)
        else:
            retry_handler = self._retry_handler

        # Execute request with retry logic
        return await retry_handler.execute_with_retry(
            self._make_request,
            method=method,
            endpoint=endpoint,
            params=params,
            data=data,
            is_private=is_private,
            rate_limit_id=rate_limit_id
        )

    async def _make_request(self,
                            method: RESTMethod,
                            endpoint: str,
                            params: Optional[Dict[str, Any]] = None,
                            data: Optional[Dict[str, Any]] = None,
                            is_private: bool = False,
                            rate_limit_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Make HTTP request to Coins.ph API.

        :param method: HTTP method
        :param endpoint: API endpoint
        :param params: Query parameters
        :param data: Request body data
        :param is_private: Whether this requires authentication
        :param rate_limit_id: Rate limit identifier
        :return: Response data
        """
        await self._ensure_session()

        # Build URL
        url = self._build_url(endpoint, is_private)

        # Prepare request parameters
        request_params = params or {}
        request_data = data
        headers = {}

        # Add authentication if required
        if is_private and self._auth:
            if method == RESTMethod.POST:
                request_data = self._auth.add_auth_to_params(request_data or {})
            else:
                request_params = self._auth.add_auth_to_params(request_params)

            headers.update(self._auth.header_for_authentication())

        # Apply rate limiting
        rate_limit_context = None
        if self._throttler and rate_limit_id:
            rate_limit_context = self._throttler.execute_task(limit_id=rate_limit_id)

        # Enhanced request logging
        request_id = self._request_logger.log_request(
            method=method.value,
            url=url,
            headers=headers,
            params=request_params,
            data=request_data
        )

        # Start debug tracking if enabled
        if self._debug_logger:
            endpoint = endpoint or url.split('/')[-1]
            self._debug_logger.start_request_tracking(request_id, method.value, endpoint)

        try:
            # Execute request with rate limiting
            if rate_limit_context:
                async with rate_limit_context:
                    response = await self._execute_request(
                        method, url, request_params, request_data, headers
                    )
            else:
                response = await self._execute_request(
                    method, url, request_params, request_data, headers
                )

            # Log successful response (basic logging, detailed logging is in _execute_request)
            if self._debug_logger:
                self._debug_logger.finish_request_tracking(request_id, 200)

            return response

        except CoinsxyzAPIError as e:
            # Log API error response
            if self._debug_logger:
                self._debug_logger.finish_request_tracking(request_id, e.status_code or 0, e)
            raise
        except asyncio.TimeoutError:
            error = CoinsxyzNetworkError("Request timeout", status_code=408)
            if self._debug_logger:
                self._debug_logger.finish_request_tracking(request_id, 408, error)
            raise error
        except aiohttp.ClientError as e:
            error = CoinsxyzNetworkError(f"Network error: {str(e)}")
            if self._debug_logger:
                self._debug_logger.finish_request_tracking(request_id, 0, error)
            raise error
        except Exception as e:
            error = CoinsxyzAPIError(f"Unexpected error: {str(e)}")
            if self._debug_logger:
                self._debug_logger.finish_request_tracking(request_id, 0, error)
            self._logger.error(f"Unexpected error in API request: {e}")
            raise error

    async def _execute_request(self,
                               method: RESTMethod,
                               url: str,
                               params: Dict[str, Any],
                               data: Optional[Dict[str, Any]],
                               headers: Dict[str, str]) -> Dict[str, Any]:
        """
        Execute the actual HTTP request.

        :param method: HTTP method
        :param url: Request URL
        :param params: Query parameters
        :param data: Request body data
        :param headers: Request headers
        :return: Response data
        """
        request_kwargs = {
            "params": params,
            "headers": headers
        }

        if method in [RESTMethod.POST, RESTMethod.PUT, RESTMethod.DELETE] and data:
            request_kwargs["json"] = data

        async with self._session.request(method.value, url, **request_kwargs) as response:
            response_text = await response.text()

            # Log response details
            self._logger.debug(f"Response status: {response.status}")
            self._logger.debug(f"Response headers: {dict(response.headers)}")
            self._logger.debug(f"Response body: {response_text[:1000]}...")  # Truncate long responses

            # Parse response
            try:
                response_data = json.loads(response_text) if response_text else {}
            except json.JSONDecodeError:
                response_data = {"raw_response": response_text}

            # Handle error responses
            # Coins.ph returns errors with HTTP 200 but error codes in response body
            if not response.ok or (response_data.get("code") and response_data.get("code") < 0):
                error = self._parse_error_response(response.status, response_data)
                self._logger.error(f"API error: {error}")
                raise error

            return response_data

    # Public API methods
    async def ping(self) -> Dict[str, Any]:
        """Test connectivity to the API."""
        return await self._make_request(
            method=RESTMethod.GET,
            endpoint=CONSTANTS.PING_PATH_URL,
            rate_limit_id=CONSTANTS.PING_PATH_URL
        )

    async def get_server_time(self) -> Dict[str, Any]:
        """Get server time."""
        return await self._make_request(
            method=RESTMethod.GET,
            endpoint=CONSTANTS.SERVER_TIME_PATH_URL,
            rate_limit_id=CONSTANTS.SERVER_TIME_PATH_URL
        )

    async def get_exchange_info(self) -> Dict[str, Any]:
        """Get exchange information including trading pairs and rules."""
        return await self._make_request(
            method=RESTMethod.GET,
            endpoint=CONSTANTS.EXCHANGE_INFO_PATH_URL,
            rate_limit_id=CONSTANTS.EXCHANGE_INFO_PATH_URL
        )

    async def get_order_book(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """Get order book for a symbol."""
        params = {"symbol": symbol, "limit": limit}
        return await self._make_request(
            method=RESTMethod.GET,
            endpoint=CONSTANTS.SNAPSHOT_PATH_URL,
            params=params,
            rate_limit_id=CONSTANTS.SNAPSHOT_PATH_URL
        )

    async def get_recent_trades(self, symbol: str, limit: int = 500) -> Dict[str, Any]:
        """Get recent trades for a symbol."""
        params = {"symbol": symbol, "limit": limit}
        return await self._make_request(
            method=RESTMethod.GET,
            endpoint=CONSTANTS.TRADES_PATH_URL,
            params=params,
            rate_limit_id=CONSTANTS.TRADES_PATH_URL
        )

    # Private API methods (require authentication)
    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information."""
        return await self._make_request(
            method=RESTMethod.GET,
            endpoint=CONSTANTS.ACCOUNTS_PATH_URL,
            is_private=True,
            rate_limit_id=CONSTANTS.ACCOUNTS_PATH_URL
        )

    async def place_order(self, order_params: Dict[str, Any]) -> Dict[str, Any]:
        """Place a new order."""
        return await self._make_request(
            method=RESTMethod.POST,
            endpoint=CONSTANTS.ORDER_PATH_URL,
            data=order_params,
            is_private=True,
            rate_limit_id=CONSTANTS.ORDER_PATH_URL
        )

    async def cancel_order(self, symbol: str, order_id: Optional[str] = None,
                           orig_client_order_id: Optional[str] = None) -> Dict[str, Any]:
        """Cancel an order."""
        params = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id

        return await self._make_request(
            method=RESTMethod.DELETE,
            endpoint=CONSTANTS.ORDER_PATH_URL,
            params=params,
            is_private=True,
            rate_limit_id=CONSTANTS.ORDER_PATH_URL
        )

    async def get_order_status(self, symbol: str, order_id: Optional[str] = None,
                               orig_client_order_id: Optional[str] = None) -> Dict[str, Any]:
        """Get order status."""
        params = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id

        return await self._make_request(
            method=RESTMethod.GET,
            endpoint=CONSTANTS.ORDER_PATH_URL,
            params=params,
            is_private=True,
            rate_limit_id=CONSTANTS.ORDER_PATH_URL
        )

    async def get_my_trades(self, symbol: str, limit: int = 500) -> Dict[str, Any]:
        """Get account trade history."""
        params = {"symbol": symbol, "limit": limit}
        return await self._make_request(
            method=RESTMethod.GET,
            endpoint=CONSTANTS.MY_TRADES_PATH_URL,
            params=params,
            is_private=True,
            rate_limit_id=CONSTANTS.MY_TRADES_PATH_URL
        )

    # Performance and logging methods

    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get API performance statistics.

        :return: Dictionary with performance metrics
        """
        return self._request_logger.get_performance_stats()

    def log_performance_summary(self) -> None:
        """Log performance statistics summary."""
        self._request_logger.log_performance_summary()

    def reset_performance_stats(self) -> None:
        """Reset performance statistics."""
        self._request_logger.reset_stats()

    def get_active_requests(self) -> Dict[str, Dict[str, Any]]:
        """
        Get currently active (unfinished) requests.

        :return: Dictionary of active requests
        """
        if self._debug_logger:
            return self._debug_logger.get_active_requests()
        return {}

    # Retry Statistics and Configuration
    # ==================================

    def get_retry_stats(self) -> Dict[str, int]:
        """
        Get retry statistics from the retry handler.

        :return: Dictionary of retry statistics
        """
        return self._retry_handler.get_retry_stats()

    def reset_retry_stats(self):
        """Reset retry statistics."""
        self._retry_handler.reset_stats()

    def update_retry_config(self, config: RetryConfig):
        """
        Update the retry configuration.

        :param config: New retry configuration
        """
        self._retry_handler = CoinsxyzRetryHandler(config)

    # Convenience Methods with Retry Logic
    # ===================================

    async def get_with_retry(self,
                             endpoint: str,
                             params: Optional[Dict[str, Any]] = None,
                             is_private: bool = False,
                             rate_limit_id: Optional[str] = None,
                             retry_config: Optional[RetryConfig] = None) -> Dict[str, Any]:
        """
        Make a GET request with retry logic.

        :param endpoint: API endpoint path
        :param params: Query parameters
        :param is_private: Whether this is a private endpoint
        :param rate_limit_id: Rate limit identifier
        :param retry_config: Custom retry configuration
        :return: API response
        """
        return await self.request_with_retry(
            method=RESTMethod.GET,
            endpoint=endpoint,
            params=params,
            is_private=is_private,
            rate_limit_id=rate_limit_id,
            retry_config=retry_config
        )

    async def post_with_retry(self,
                              endpoint: str,
                              data: Optional[Dict[str, Any]] = None,
                              params: Optional[Dict[str, Any]] = None,
                              is_private: bool = True,
                              rate_limit_id: Optional[str] = None,
                              retry_config: Optional[RetryConfig] = None) -> Dict[str, Any]:
        """
        Make a POST request with retry logic.

        :param endpoint: API endpoint path
        :param data: Request body data
        :param params: Query parameters
        :param is_private: Whether this is a private endpoint
        :param rate_limit_id: Rate limit identifier
        :param retry_config: Custom retry configuration
        :return: API response
        """
        return await self.request_with_retry(
            method=RESTMethod.POST,
            endpoint=endpoint,
            data=data,
            params=params,
            is_private=is_private,
            rate_limit_id=rate_limit_id,
            retry_config=retry_config
        )

    async def delete_with_retry(self,
                                endpoint: str,
                                params: Optional[Dict[str, Any]] = None,
                                is_private: bool = True,
                                rate_limit_id: Optional[str] = None,
                                retry_config: Optional[RetryConfig] = None) -> Dict[str, Any]:
        """
        Make a DELETE request with retry logic.

        :param endpoint: API endpoint path
        :param params: Query parameters
        :param is_private: Whether this is a private endpoint
        :param rate_limit_id: Rate limit identifier
        :param retry_config: Custom retry configuration
        :return: API response
        """
        return await self.request_with_retry(
            method=RESTMethod.DELETE,
            endpoint=endpoint,
            params=params,
            is_private=is_private,
            rate_limit_id=rate_limit_id,
            retry_config=retry_config
        )
