"""
Web utilities for Deluthium DEX connector.
"""

import time
from typing import Any, Dict, Optional

import hummingbot.connector.exchange.deluthium.deluthium_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class DeluthiumRESTPreProcessor(RESTPreProcessorBase):
    """Pre-processor for Deluthium REST API requests."""

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        request.headers["Content-Type"] = "application/json"
        return request


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """Build public REST API URL."""
    return rest_url(path_url, domain)


def private_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """Build private REST API URL."""
    return rest_url(path_url, domain)


def rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """Build REST API URL."""
    base_url = CONSTANTS.BASE_URL
    return f"{base_url}{path_url}"


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    auth: Optional[AuthBase] = None
) -> WebAssistantsFactory:
    """Build web assistants factory with throttler and auth."""
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[DeluthiumRESTPreProcessor()],
        auth=auth
    )
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(
    throttler: AsyncThrottler
) -> WebAssistantsFactory:
    """Build API factory without time synchronizer."""
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[DeluthiumRESTPreProcessor()]
    )
    return api_factory


def create_throttler() -> AsyncThrottler:
    """Create async throttler with Deluthium rate limits."""
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(throttler: AsyncThrottler, domain: str) -> float:
    """Get current server time (returns local time)."""
    return time.time()


def is_exchange_information_valid(pair_info: Dict[str, Any]) -> bool:
    """Verify if a trading pair is valid and enabled."""
    is_enabled = pair_info.get("is_enabled", True)
    return is_enabled
