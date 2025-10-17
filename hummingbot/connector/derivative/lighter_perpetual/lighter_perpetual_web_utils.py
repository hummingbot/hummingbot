from typing import Any, Dict, Optional

from hummingbot.connector.derivative.lighter_perpetual import lighter_perpetual_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class LighterPerpetualRESTPreProcessor(RESTPreProcessorBase):
    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        # Generates generic headers required by Lighter
        headers_generic = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        # Add HB identifier
        headers_generic.update(get_hb_id_headers())
        request.headers = dict(
            list(request.headers.items()) + list(headers_generic.items())
        )
        return request


def get_hb_id_headers() -> Dict[str, Any]:
    """
    Headers signature to identify user as an HB liquidity provider.
    """
    return {
        "User-Agent": "hummingbot-client",
    }


def public_rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
    """
    Creates a full URL for provided public REST endpoint
    """
    base_url = CONSTANTS.BASE_URL if domain == CONSTANTS.DOMAIN else CONSTANTS.TESTNET_BASE_URL
    return base_url + path_url


def private_rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
    """
    Creates a full URL for provided private REST endpoint
    """
    base_url = CONSTANTS.BASE_URL if domain == CONSTANTS.DOMAIN else CONSTANTS.TESTNET_BASE_URL
    return base_url + path_url


def wss_url(domain: str = CONSTANTS.DOMAIN) -> str:
    """
    Creates a full WebSocket URL
    """
    return CONSTANTS.WS_URL if domain == CONSTANTS.DOMAIN else CONSTANTS.TESTNET_WS_URL


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    domain: str = CONSTANTS.DOMAIN,
    auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[LighterPerpetualRESTPreProcessor()]
    )
    return api_factory


def create_throttler(domain: str = CONSTANTS.DOMAIN) -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None,
    domain: str = CONSTANTS.DOMAIN,
) -> float:
    import time
    return time.time()

