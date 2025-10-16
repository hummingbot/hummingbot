"""
Web utilities for Coins.ph Exchange Connector

This module provides web-related utilities including URL construction,
web assistant factory creation, and HTTP client configuration.
"""

from typing import Any, Callable, Dict, Optional

import aiohttp

from hummingbot.connector.exchange.coinsxyz import coinsxyz_constants as CONSTANTS
from hummingbot.connector.exchange.coinsxyz.coinsxyz_retry_utils import (
    CoinsxyzRetryHandler,
    RetryConfig,
    RetryConfigs
)
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class CoinsxyzRESTPreProcessor(RESTPreProcessorBase):
    """
    Pre-processor for Coins.xyz REST API requests.

    Handles request preprocessing such as URL construction and header management.
    """

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        """
        Pre-process REST requests before sending to Coins.xyz API.

        :param request: The request to pre-process
        :return: The processed request
        """
        # Add any common headers or preprocessing logic here
        if request.headers is None:
            request.headers = {}

        # Add User-Agent header if not present
        if "User-Agent" not in request.headers:
            request.headers["User-Agent"] = "Hummingbot/CoinsxyzConnector"

        return request


def rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Construct URL for REST API endpoints.

    :param path_url: The API endpoint path
    :param domain: The domain to use (default: "com")
    :return: Complete REST API URL
    """
    base_url = CONSTANTS.REST_URL
    return f"{base_url}{path_url}"


def wss_url(path_url: str = "", domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Construct URL for WebSocket endpoints.

    :param path_url: The WebSocket endpoint path
    :param domain: The domain to use (default: "com")
    :return: Complete WebSocket URL
    """
    base_url = CONSTANTS.WSS_URL
    return f"{base_url}{path_url}"


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Construct URL for public REST API endpoints.

    :param path_url: The API endpoint path
    :param domain: The domain to use (default: "com")
    :return: Complete URL for the public API endpoint
    """
    base_url = CONSTANTS.REST_URL
    api_version = CONSTANTS.PUBLIC_API_VERSION
    return f"{base_url}{api_version}{path_url}"


def private_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Construct URL for private REST API endpoints.

    :param path_url: The API endpoint path
    :param domain: The domain to use (default: "com")
    :return: Complete URL for the private API endpoint
    """
    base_url = CONSTANTS.REST_URL
    api_version = CONSTANTS.PRIVATE_API_VERSION
    return f"{base_url}{api_version}{path_url}"


def websocket_url(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Construct WebSocket URL for real-time data streams.

    :param domain: The domain to use (default: "com")
    :return: WebSocket URL
    """
    return CONSTANTS.WSS_URL


async def get_current_server_time(
    throttler: AsyncThrottler,
    domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> float:
    """
    Get current server time from Coins.ph API.

    This function is used for time synchronization to ensure
    accurate timestamps in authenticated requests.

    :param throttler: Rate limiter for API requests
    :param domain: The domain to use
    :return: Server timestamp as float
    """
    url = public_rest_url(CONSTANTS.SERVER_TIME_PATH_URL, domain)

    async with aiohttp.ClientSession() as session:
        async with throttler.execute_task(limit_id=CONSTANTS.SERVER_TIME_PATH_URL):
            async with session.get(url) as response:
                response_data = await response.json()
                # Coins.ph returns timestamp in milliseconds
                return float(response_data.get("serverTime", 0)) / 1000.0


async def validate_server_time_sync(
    throttler: AsyncThrottler,
    domain: str = CONSTANTS.DEFAULT_DOMAIN,
    max_time_diff: float = 30.0
) -> tuple[bool, float]:
    """
    Validate server time synchronization.

    :param throttler: Rate limiter for API requests
    :param domain: The domain to use
    :param max_time_diff: Maximum acceptable time difference in seconds
    :return: Tuple of (is_synchronized, time_difference)
    """
    import time

    try:
        local_time_before = time.time()
        server_time = await get_current_server_time(throttler, domain)
        local_time_after = time.time()

        # Estimate network latency and adjust
        network_latency = (local_time_after - local_time_before) / 2
        adjusted_local_time = local_time_before + network_latency

        time_diff = abs(server_time - adjusted_local_time)
        is_synchronized = time_diff <= max_time_diff

        return is_synchronized, time_diff

    except Exception:
        return False, float('inf')


def create_time_synchronizer(domain: str = CONSTANTS.DEFAULT_DOMAIN):
    """
    Create a time synchronizer instance for Coins.ph.

    :param domain: The domain to use
    :return: CoinsxyzTimeSynchronizer instance
    """
    from hummingbot.connector.exchange.coinsxyz.coinsxyz_time_synchronizer import CoinsxyzTimeSynchronizer
    return CoinsxyzTimeSynchronizer(domain=domain)


def build_api_factory(
    throttler: AsyncThrottler,
    time_synchronizer: Optional[Callable[[], float]] = None,
    domain: str = CONSTANTS.DEFAULT_DOMAIN,
    auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    """
    Build and configure the web assistants factory for Coins.xyz API.

    :param throttler: Rate limiter for API requests
    :param time_synchronizer: Time synchronization function
    :param domain: The domain to use
    :param auth: Authentication handler
    :return: Configured WebAssistantsFactory
    """
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[CoinsxyzRESTPreProcessor()],
    )
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(
    throttler: AsyncThrottler,
    domain: str = CONSTANTS.DEFAULT_DOMAIN,
    auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    """
    Build web assistants factory without time synchronizer pre-processor.

    This is useful for initial setup or when time synchronization is not needed.

    :param throttler: Rate limiter for API requests
    :param domain: The domain to use
    :param auth: Authentication handler
    :return: Configured WebAssistantsFactory
    """
    return build_api_factory(
        throttler=throttler,
        domain=domain,
        auth=auth,
    )


def create_throttler() -> AsyncThrottler:
    """
    Create and configure the rate limiter for Coins.xyz API.

    :return: Configured AsyncThrottler with Coins.xyz rate limits
    """
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


def create_retry_handler(config: Optional[RetryConfig] = None) -> CoinsxyzRetryHandler:
    """
    Create a retry handler for Coins.xyz API requests.

    :param config: Retry configuration, uses standard if None
    :return: Configured retry handler
    """
    return CoinsxyzRetryHandler(config or RetryConfigs.STANDARD)


async def api_request(
    method: RESTMethod,
    url: str,
    throttler: AsyncThrottler,
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    limit_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Make an API request to Coins.xyz with proper rate limiting.

    :param method: HTTP method (GET, POST, DELETE, etc.)
    :param url: Complete URL for the request
    :param throttler: Rate limiter
    :param params: Query parameters
    :param data: Request body data
    :param headers: Request headers
    :param limit_id: Rate limit identifier
    :return: API response as dictionary
    """
    async with aiohttp.ClientSession() as session:
        async with throttler.execute_task(limit_id=limit_id or url):
            request_kwargs = {
                "params": params,
                "headers": headers,
            }

            if method in [RESTMethod.POST, RESTMethod.PUT]:
                request_kwargs["json"] = data

            async with session.request(method.value, url, **request_kwargs) as response:
                response.raise_for_status()
                return await response.json()


def get_rest_url_for_endpoint(
    endpoint: str,
    trading_pair: Optional[str] = None,
    domain: str = CONSTANTS.DEFAULT_DOMAIN,
    is_private: bool = False,
) -> str:
    """
    Get the complete REST URL for a specific endpoint.

    :param endpoint: The API endpoint
    :param trading_pair: Trading pair if needed for the endpoint
    :param domain: The domain to use
    :param is_private: Whether this is a private endpoint
    :return: Complete URL for the endpoint
    """
    if is_private:
        base_url = private_rest_url(endpoint, domain)
    else:
        base_url = public_rest_url(endpoint, domain)

    if trading_pair:
        # Add trading pair to URL if needed
        symbol = trading_pair.replace("-", "")
        base_url = base_url.replace("{symbol}", symbol)

    return base_url


def format_trading_pair_for_url(trading_pair: str) -> str:
    """
    Format trading pair for use in URLs.

    :param trading_pair: Trading pair in Hummingbot format (BASE-QUOTE)
    :return: Trading pair formatted for Coins.ph URLs
    """
    return trading_pair.replace("-", "").upper()
