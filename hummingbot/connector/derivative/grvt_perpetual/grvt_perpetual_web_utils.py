import logging
from typing import Any, Callable, Dict, Optional

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS
import hummingbot.core.web_assistant.web_assistants_factory as web_assistants_factory
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN, rpc_type: str = CONSTANTS.GRVT_MARKET_DATA_RPC) -> str:
    base_url = get_rest_url_multiplier(domain, rpc_type)
    return base_url + path_url


def private_rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN, rpc_type: str = CONSTANTS.GRVT_TRADE_DATA_RPC) -> str:
    base_url = get_rest_url_multiplier(domain, rpc_type)
    return base_url + path_url


def get_rest_url_multiplier(domain: str, rpc_type: str) -> str:
    if domain == CONSTANTS.DOMAIN:
        if rpc_type == CONSTANTS.GRVT_MARKET_DATA_RPC:
            return CONSTANTS.PROD_MARKET_URL
        elif rpc_type == CONSTANTS.GRVT_TRADE_DATA_RPC:
            return CONSTANTS.PROD_TRADE_URL
        else:
            return CONSTANTS.PROD_EDGE_URL
    else:
        if rpc_type == CONSTANTS.GRVT_MARKET_DATA_RPC:
            return CONSTANTS.TESTNET_MARKET_URL
        elif rpc_type == CONSTANTS.GRVT_TRADE_DATA_RPC:
            return CONSTANTS.TESTNET_TRADE_URL
        else:
            return CONSTANTS.TESTNET_EDGE_URL


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    time_synchronizer: Optional[Any] = None,
    domain: str = CONSTANTS.DOMAIN,
    time_provider: Optional[Callable] = None,
    auth: Optional[Any] = None,
) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or time_provider
    api_factory = web_assistants_factory.WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[],
    )
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(
    throttler: AsyncThrottler,
    auth: Optional[Any] = None,
) -> WebAssistantsFactory:
    api_factory = web_assistants_factory.WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[],
    )
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None,
    domain: str = CONSTANTS.DOMAIN,
) -> float:
    # GRVT does not have a dedicated server time endpoint. We can use the timestamp from the response headers or system time.
    # We will just return 0 for now so the time synchronizer uses system time, or we can fetch a public endpoint and use its header.
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    # Pinging market data for a quick response to check its Date header
    url = public_rest_url(CONSTANTS.MARK_PRICE_URL, domain=domain)
    # Using the empty request since there's no /ping
    request = RESTRequest(method=RESTMethod.POST, url=url, data={})
    
    # Normally we would parse Date from headers, but for now fallback to local time if not possible
    import time
    return time.time() * 1000
