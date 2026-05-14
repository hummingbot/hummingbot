from decimal import ROUND_DOWN, Decimal
from typing import Any, Dict, Optional

import hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class AevoPerpetualRESTPreProcessor(RESTPreProcessorBase):

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        request.headers["Content-Type"] = "application/json"
        return request


def private_rest_url(*args, **kwargs) -> str:
    return rest_url(*args, **kwargs)


def public_rest_url(*args, **kwargs) -> str:
    return rest_url(*args, **kwargs)


def rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN):
    base_url = CONSTANTS.BASE_URL if domain == CONSTANTS.DEFAULT_DOMAIN else CONSTANTS.TESTNET_BASE_URL
    return base_url + path_url


def wss_url(domain: str = CONSTANTS.DEFAULT_DOMAIN):
    base_ws_url = CONSTANTS.WSS_URL if domain == CONSTANTS.DEFAULT_DOMAIN else CONSTANTS.TESTNET_WSS_URL
    return base_ws_url


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        auth: Optional[AuthBase] = None) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[AevoPerpetualRESTPreProcessor()],
        auth=auth)

    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[AevoPerpetualRESTPreProcessor()])

    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


def is_exchange_information_valid(rule: Dict[str, Any]) -> bool:
    return bool(rule.get("is_active", False))


def decimal_to_int(value: Decimal, decimals: int = 6) -> int:
    scale = Decimal(10) ** decimals
    return int((value * scale).quantize(Decimal("1"), rounding=ROUND_DOWN))


async def get_current_server_time(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> float:
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    response = await rest_assistant.execute_request(
        url=public_rest_url(path_url=CONSTANTS.PING_PATH_URL, domain=domain),
        method=RESTMethod.GET,
        throttler_limit_id=CONSTANTS.PING_PATH_URL,
    )
    server_time = response.get("timestamp")

    if server_time is None:
        raise KeyError(f"Unexpected server time response: {response}")
    return float(server_time)
