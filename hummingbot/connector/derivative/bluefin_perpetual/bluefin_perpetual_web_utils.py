import time
from typing import Optional

import hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class BluefinPerpetualRESTPreProcessor(RESTPreProcessorBase):
    """REST pre-processor for Bluefin API requests."""

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        else:
            request.headers = dict(request.headers)
        request.headers["Content-Type"] = "application/json"
        return request


def get_rest_url_for_endpoint(endpoint: str, domain: str = CONSTANTS.DOMAIN) -> str:
    """
    Get the full REST URL for an endpoint based on domain.

    Note: The Bluefin SDK handles all REST communication internally.
    This is provided for compatibility with hummingbot's web assistant pattern.
    """
    env_name = CONSTANTS.MAINNET_ENV_NAME if domain == CONSTANTS.DOMAIN else CONSTANTS.STAGING_ENV_NAME
    base_url = CONSTANTS.get_rest_url_for_env(env_name, service="api")
    return base_url + endpoint


def get_ws_url(domain: str = CONSTANTS.DOMAIN, stream_type: str = "market") -> str:
    """
    Get the WebSocket URL based on domain and stream type.

    Note: The Bluefin SDK handles all WebSocket communication internally.
    This is provided for compatibility with hummingbot's web assistant pattern.
    """
    env_name = CONSTANTS.MAINNET_ENV_NAME if domain == CONSTANTS.DOMAIN else CONSTANTS.STAGING_ENV_NAME
    return CONSTANTS.get_ws_url_for_env(env_name, stream_type)


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        auth: Optional[AuthBase] = None) -> WebAssistantsFactory:
    """Build web assistants factory with throttler and auth."""
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[BluefinPerpetualRESTPreProcessor()],
        auth=auth)
    return api_factory


def create_throttler() -> AsyncThrottler:
    """Create async throttler with rate limits."""
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(throttler: AsyncThrottler, domain: str) -> float:
    """
    Get current server time.

    Note: Returns local time as Bluefin SDK handles time synchronization internally.
    """
    return time.time()
