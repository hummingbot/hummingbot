import time
from typing import Optional

import hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_rest_url(endpoint: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Builds a full URL for a public (unauthenticated) REST endpoint.

    :param endpoint: path such as ``api/v2.3/market_summary``
    :param domain: connector domain key; drives prod vs sandbox base URL
    :return: full URL string
    """
    base = CONSTANTS.REST_URLS.get(domain, CONSTANTS.REST_URLS[CONSTANTS.DEFAULT_DOMAIN])
    if not base.endswith("/") and not endpoint.startswith("/"):
        endpoint = "/" + endpoint
    return base + endpoint


def private_rest_url(endpoint: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Builds a full URL for an authenticated REST endpoint.
    LMEX uses the same base URL for both public and private endpoints.
    """
    return public_rest_url(endpoint, domain)


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    auth: Optional[AuthBase] = None,
    domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(throttler=throttler, auth=auth)
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None,
    domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> float:
    """
    LMEX Futures does not expose a dedicated server-time endpoint; fall back to
    local wall-clock time.  The connector uses nonce-based auth, so small clock
    skew is acceptable.
    """
    return time.time()
