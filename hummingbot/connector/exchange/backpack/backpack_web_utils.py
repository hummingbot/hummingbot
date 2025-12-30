import time
from typing import Any, Dict, Optional

import hummingbot.connector.exchange.backpack.backpack_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class BackpackRESTPreProcessor(RESTPreProcessorBase):
    """Pre-processor to add Content-Type header to all REST requests."""

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        request.headers["Content-Type"] = "application/json"
        return request


def private_rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
    """Build private REST endpoint URL."""
    return rest_url(path_url, domain)


def public_rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
    """Build public REST endpoint URL."""
    return rest_url(path_url, domain)


def rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
    """
    Build full REST URL from path and domain.

    Args:
        path_url: The API endpoint path (e.g., "/api/v1/markets")
        domain: The domain name ("backpack" or "backpack_testnet")

    Returns:
        Full URL string
    """
    base_url = CONSTANTS.BASE_URL if domain == CONSTANTS.DOMAIN else CONSTANTS.TESTNET_BASE_URL
    return base_url + path_url


def wss_url(domain: str = CONSTANTS.DOMAIN) -> str:
    """
    Get WebSocket URL for the given domain.

    Args:
        domain: The domain name ("backpack" or "backpack_testnet")

    Returns:
        WebSocket URL string
    """
    return CONSTANTS.WS_URL if domain == CONSTANTS.DOMAIN else CONSTANTS.TESTNET_WS_URL


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    """
    Build the API factory for REST and WebSocket connections.

    Args:
        throttler: Rate limiter instance (created if None)
        auth: Authentication handler

    Returns:
        Configured WebAssistantsFactory
    """
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[BackpackRESTPreProcessor()],
        auth=auth,
    )
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(
    throttler: AsyncThrottler,
) -> WebAssistantsFactory:
    """
    Build API factory without time synchronizer (for public endpoints).

    Args:
        throttler: Rate limiter instance

    Returns:
        Configured WebAssistantsFactory
    """
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[BackpackRESTPreProcessor()],
    )
    return api_factory


def create_throttler() -> AsyncThrottler:
    """Create rate limiter with Backpack's rate limits."""
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None,
    domain: str = CONSTANTS.DOMAIN,
) -> float:
    """
    Fetch current server time from Backpack API.

    Args:
        throttler: Rate limiter instance
        domain: The domain name

    Returns:
        Server timestamp as float
    """
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    response = await rest_assistant.execute_request(
        url=public_rest_url(path_url=CONSTANTS.TIME_URL, domain=domain),
        method=RESTMethod.GET,
        throttler_limit_id=CONSTANTS.TIME_URL,
    )

    server_time = None
    if isinstance(response, dict):
        for key in ("serverTime", "server_time", "time", "timestamp", "ts"):
            if key in response:
                server_time = response[key]
                break
    else:
        server_time = response

    try:
        server_time = float(server_time)
    except Exception:
        server_time = time.time() * 1e3

    # Normalize to milliseconds
    if server_time > 1e14:
        server_time /= 1000.0  # microseconds to milliseconds
    elif server_time < 1e11:
        server_time *= 1000.0  # seconds to milliseconds

    return server_time


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Check if a trading pair is enabled for trading.

    Args:
        exchange_info: Market information from the exchange

    Returns:
        True if the market is enabled
    """
    # Backpack markets are enabled if they exist in the response
    return True


def convert_to_exchange_symbol(hb_trading_pair: str) -> str:
    """
    Convert Hummingbot trading pair format to Backpack format.

    Args:
        hb_trading_pair: Trading pair in Hummingbot format (e.g., "BTC-USDC")

    Returns:
        Trading pair in Backpack format (e.g., "BTC_USDC")
    """
    return hb_trading_pair.replace("-", "_")


def convert_from_exchange_symbol(exchange_symbol: str) -> str:
    """
    Convert Backpack symbol to Hummingbot trading pair format.

    Args:
        exchange_symbol: Trading pair in Backpack format (e.g., "BTC_USDC")

    Returns:
        Trading pair in Hummingbot format (e.g., "BTC-USDC")
    """
    return exchange_symbol.replace("_", "-")


def get_base_quote_from_symbol(symbol: str) -> tuple[str, str]:
    """
    Extract base and quote assets from a Backpack symbol.

    Args:
        symbol: Trading pair (e.g., "BTC_USDC" or "SOL_USDC_PERP")

    Returns:
        Tuple of (base_asset, quote_asset)
    """
    parts = symbol.split("_")
    if len(parts) >= 2:
        base = parts[0]
        quote = parts[1]
        return base, quote
    raise ValueError(f"Invalid symbol format: {symbol}")
