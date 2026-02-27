import time
from typing import Optional

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class GrvtPerpetualRESTPreProcessor(RESTPreProcessorBase):
    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        request.headers["Content-Type"] = "application/json"
        return request


def public_rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
    return rest_url(path_url, domain)


def private_rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
    return rest_url(path_url, domain)


def rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
    is_testnet = domain == CONSTANTS.TESTNET_DOMAIN
    # Route to the correct base URL based on path prefix
    if path_url.startswith("auth/"):
        base = CONSTANTS.TESTNET_BASE_EDGE_URL if is_testnet else CONSTANTS.PERPETUAL_BASE_EDGE_URL
    elif path_url.startswith("full/v1/all_instruments") or \
            path_url.startswith("full/v1/instrument") or \
            path_url.startswith("full/v1/ticker") or \
            path_url.startswith("full/v1/mini") or \
            path_url.startswith("full/v1/book") or \
            path_url.startswith("full/v1/trade") or \
            path_url.startswith("full/v1/kline") or \
            path_url.startswith("full/v1/funding"):
        base = CONSTANTS.TESTNET_BASE_MARKET_URL if is_testnet else CONSTANTS.PERPETUAL_BASE_MARKET_URL
    else:
        base = CONSTANTS.TESTNET_BASE_TRADE_URL if is_testnet else CONSTANTS.PERPETUAL_BASE_TRADE_URL
    return f"{base}/{path_url}"


def wss_market_url(domain: str = CONSTANTS.DOMAIN) -> str:
    is_testnet = domain == CONSTANTS.TESTNET_DOMAIN
    return CONSTANTS.TESTNET_WS_MARKET_URL if is_testnet else CONSTANTS.PERPETUAL_WS_MARKET_URL


def wss_trade_url(domain: str = CONSTANTS.DOMAIN) -> str:
    is_testnet = domain == CONSTANTS.TESTNET_DOMAIN
    return CONSTANTS.TESTNET_WS_TRADE_URL if is_testnet else CONSTANTS.PERPETUAL_WS_TRADE_URL


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        auth: Optional[AuthBase] = None) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[GrvtPerpetualRESTPreProcessor()],
        auth=auth)
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(
        throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[GrvtPerpetualRESTPreProcessor()])
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(throttler, domain) -> float:
    return time.time()


def is_exchange_information_valid(instrument: dict) -> bool:
    """Only include active perpetual instruments."""
    return (
        instrument.get("isActive", False)
        and instrument.get("instrumentType") == "PERPETUAL"
    )
