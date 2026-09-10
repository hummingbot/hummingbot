import time
from typing import Any, Dict, Optional

import hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class KalshiPerpetualRESTPreProcessor(RESTPreProcessorBase):

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        # Kalshi takes JSON bodies on every write endpoint; GET parameters go in the query string.
        request.headers["Content-Type"] = "application/json"
        return request


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return CONSTANTS.REST_URLS[domain] + path_url


def private_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    # Kalshi serves public and private endpoints from the same base URL.
    return public_rest_url(path_url=path_url, domain=domain)


def wss_url(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return CONSTANTS.WSS_URLS[domain]


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        auth: Optional[AuthBase] = None) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[KalshiPerpetualRESTPreProcessor()])
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


def is_exchange_information_valid(market: Dict[str, Any]) -> bool:
    """
    Only active KX<ASSET>PERP markets are tradable perpetuals (inactive and closed ones are skipped).

    :param market: a market from the /margin/markets response
    """
    ticker = market.get("ticker", "")
    return (market.get("status") == "active"
            and ticker.startswith(CONSTANTS.MARKET_TICKER_PREFIX)
            and ticker.endswith(CONSTANTS.MARKET_TICKER_SUFFIX))


async def get_current_server_time(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> float:
    # Kalshi has no server-time endpoint, so local time is the reference. The base class still calls this on every
    # status poll, and TimeSynchronizer expects milliseconds: returning seconds would skew the offset by ~1.7e12 ms.
    return time.time() * 1e3
