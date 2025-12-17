from typing import Any, Dict, Optional

import hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class LighterPerpetualRESTPreProcessor(RESTPreProcessorBase):
    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        request.headers = request.headers or {}
        request.headers.setdefault("Content-Type", "application/json")
        return request


def rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    base_url = CONSTANTS.REST_URLS.get(
        domain, CONSTANTS.REST_URLS[CONSTANTS.DEFAULT_DOMAIN]
    )
    return f"{base_url}{path_url}"


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return rest_url(path_url, domain)


def private_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return rest_url(path_url, domain)


def wss_url(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return CONSTANTS.WSS_URLS.get(domain, CONSTANTS.WSS_URLS[CONSTANTS.DEFAULT_DOMAIN])


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None, auth: Optional[AuthBase] = None
) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    return WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[LighterPerpetualRESTPreProcessor()],
        auth=auth,
    )


def build_api_factory_without_time_synchronizer_pre_processor(
    throttler: AsyncThrottler,
) -> WebAssistantsFactory:
    return WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[LighterPerpetualRESTPreProcessor()],
    )


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(throttler: AsyncThrottler, domain: str) -> float:
    del throttler, domain
    raise NotImplementedError("Lighter does not expose a server time endpoint.")


def is_exchange_information_valid(market_info: Dict[str, Any]) -> bool:
    status = market_info.get("status", "").lower()
    return status in {"enabled", "active", "listed", ""}
