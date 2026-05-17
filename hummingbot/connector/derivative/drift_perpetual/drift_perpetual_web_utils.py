import time
from typing import Any, Dict

import hummingbot.connector.derivative.drift_perpetual.drift_perpetual_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class DriftPerpetualRESTPreProcessor(RESTPreProcessorBase):

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        request.headers["Accept"] = "application/json"
        request.headers["Content-Type"] = "application/json"
        return request


def gateway_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """Full URL for a self-hosted Drift Gateway REST endpoint (/v2/*)."""
    return CONSTANTS.DRIFT_GATEWAY_REST_URL + path_url


def dlob_rest_url(path_url: str) -> str:
    """Full URL for the hosted DLOB server (public order book / auction params)."""
    return CONSTANTS.DRIFT_DLOB_REST_URL + path_url


def data_api_url(path_url: str) -> str:
    """Full URL for the hosted Data API (historical funding rates)."""
    return CONSTANTS.DRIFT_DATA_API_URL + path_url


def build_api_factory(throttler: AsyncThrottler = None) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[DriftPerpetualRESTPreProcessor()],
    )
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    return WebAssistantsFactory(throttler=throttler)


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(throttler: AsyncThrottler = None, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> float:
    """
    Drift Gateway is operator-self-hosted (co-located with the bot), so its
    clock is the local host clock — there is no remote time endpoint to
    skew against. Return local epoch seconds; the TimeSynchronizer offset
    is therefore ~0 by construction. Kept as a coroutine for interface
    parity with other connectors' web_utils.
    """
    return time.time()


def is_exchange_information_valid(market: Dict[str, Any]) -> bool:
    """
    Verify a market is tradeable. Drift /v2/markets returns a `status`
    field; only fully-initialized perp markets are accepted.
    """
    status = str(market.get("status", "")).lower()
    return status in ("active", "initialized", "")
