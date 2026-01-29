from typing import Optional

from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    throttler = throttler or AsyncThrottler(CONSTANTS.RATE_LIMITS)
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth
    )
    return api_factory


def get_endpoint(domain: str) -> str:
    if domain == CONSTANTS.TESTNET_DOMAIN:
        return CONSTANTS.TESTNET_ENDPOINT
    return CONSTANTS.PERPETUAL_ENDPOINT
