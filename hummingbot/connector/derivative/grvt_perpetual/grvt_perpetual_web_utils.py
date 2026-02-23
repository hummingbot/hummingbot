import time
from typing import Any, Dict, Optional

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


# ---------- URL routing constants ----------

# Endpoints that go to the Market Data host (public, no auth)
_MARKET_DATA_ENDPOINTS = {
    CONSTANTS.ALL_INSTRUMENTS_URL,
    CONSTANTS.ORDERBOOK_URL,
    CONSTANTS.TICKER_URL,
    CONSTANTS.RECENT_TRADES_URL,
    CONSTANTS.FUNDING_RATE_URL,
}

# Endpoints that go to the Edge host (auth only)
_EDGE_ENDPOINTS = {
    CONSTANTS.AUTH_LOGIN_URL,
}

# Everything else goes to the Trade Data host (authenticated)


class GrvtPerpetualRESTPreProcessor(RESTPreProcessorBase):
    """
    Pre-processor that sets Content-Type for all GRVT requests.
    All GRVT REST endpoints use POST with JSON body.
    """

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        request.headers["Content-Type"] = "application/json"
        return request


def _get_host(path_url: str, domain: str) -> str:
    """
    Routes a path to the correct host based on the endpoint type.

    GRVT has three hosts:
    - Edge: auth/login only
    - Market Data: public orderbook, ticker, instruments, etc.
    - Trade Data: authenticated order placement, fills, positions, etc.
    """
    is_mainnet = domain == CONSTANTS.DOMAIN

    if path_url in _EDGE_ENDPOINTS:
        return CONSTANTS.EDGE_BASE_URL if is_mainnet else CONSTANTS.TESTNET_EDGE_BASE_URL
    elif path_url in _MARKET_DATA_ENDPOINTS:
        return CONSTANTS.MARKET_DATA_BASE_URL if is_mainnet else CONSTANTS.TESTNET_MARKET_DATA_BASE_URL
    else:
        return CONSTANTS.TRADE_BASE_URL if is_mainnet else CONSTANTS.TESTNET_TRADE_BASE_URL


def rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
    """
    Constructs the full REST URL by routing the path to the correct host.
    """
    host = _get_host(path_url, domain)
    return host + path_url


def public_rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
    """
    Constructs the full URL for public (Market Data) endpoints.
    """
    return rest_url(path_url, domain)


def private_rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
    """
    Constructs the full URL for private (Trade Data) endpoints.
    """
    return rest_url(path_url, domain)


def market_data_wss_url(domain: str = CONSTANTS.DOMAIN) -> str:
    """
    Returns the Market Data WebSocket URL (public streams).
    """
    if domain == CONSTANTS.DOMAIN:
        return CONSTANTS.MARKET_WS_FULL_URL
    return CONSTANTS.TESTNET_MARKET_WS_FULL_URL


def trade_wss_url(domain: str = CONSTANTS.DOMAIN) -> str:
    """
    Returns the Trade Data WebSocket URL (authenticated streams).
    """
    if domain == CONSTANTS.DOMAIN:
        return CONSTANTS.TRADE_WS_FULL_URL
    return CONSTANTS.TESTNET_TRADE_WS_FULL_URL


def wss_url(domain: str = CONSTANTS.DOMAIN) -> str:
    """
    Default WS URL (market data) for compatibility with framework.
    """
    return market_data_wss_url(domain)


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    """
    Creates a WebAssistantsFactory with the GRVT pre-processor.
    """
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[GrvtPerpetualRESTPreProcessor()],
        auth=auth,
    )
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(
    throttler: AsyncThrottler,
) -> WebAssistantsFactory:
    """
    Creates a WebAssistantsFactory without time synchronization (not needed
    for GRVT which uses session cookies).
    """
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[GrvtPerpetualRESTPreProcessor()],
    )
    return api_factory


def create_throttler() -> AsyncThrottler:
    """Creates a rate-limit throttler with GRVT limits."""
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None,
    domain: str = CONSTANTS.DOMAIN,
) -> float:
    """
    GRVT does not require time synchronization. Returns local time.
    """
    return time.time()


def is_exchange_information_valid(instrument: Dict[str, Any]) -> bool:
    """
    Verifies if a trading instrument is enabled for trading.

    :param instrument: the instrument information dict from GRVT API
    :return: True if the instrument is enabled, False otherwise
    """
    return instrument.get("is_active", True)
