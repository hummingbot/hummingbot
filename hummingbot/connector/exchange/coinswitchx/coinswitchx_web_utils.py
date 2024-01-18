import time
from typing import Any, Dict, Optional

import hummingbot.connector.exchange.coinswitchx.coinswitchx_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class CoinswitchxRESTPreProcessor(RESTPreProcessorBase):
    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        # Generates generic headers required by AscendEx
        headers_generic = {}
        headers_generic["Accept"] = "application/json"
        headers_generic["Content-Type"] = "application/json"
        # Headers signature to identify user as an HB liquidity provider.
        request.headers = dict(
            list(request.headers.items()) + list(headers_generic.items()) + list(get_hb_id_headers().items())
        )
        return request


def get_hb_id_headers() -> Dict[str, Any]:
    """
    Headers signature to identify user as an HB liquidity provider.

    :return: a custom HB signature header
    """
    return {
        "request-source": "hummingbot-liq-mining",
    }


def rest_url(path_url: str) -> str:
    """
    Creates a full URL for provided public REST endpoint
    :param path_url: a public REST endpoint
    :return: the full URL to the endpoint
    """
    return f"https://{CONSTANTS.REST_URL}/api/{path_url}"


def websocket_url() -> str:
    """
    Creates a full URL for provided WebSocket endpoint
    :return: the full URL to the endpoint
    """
    return f"wss://{CONSTANTS.WSS_URL}/"


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(throttler=throttler, auth=auth, rest_pre_processors=[CoinswitchxRESTPreProcessor()])
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None,
    domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> int:
    return int(time.time() * 1e3)
