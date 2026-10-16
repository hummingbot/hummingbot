from typing import Any, Callable, Dict, Optional

import hummingbot.connector.exchange.lmex.lmex_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_rest_url(endpoint: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Builds the full REST URL for a public endpoint.

    :param endpoint: path relative to the base URL (with or without a leading slash)
    :param domain: '' for production, 'sandbox' for test environment
    :return: full URL string
    """
    base = CONSTANTS.REST_URLS.get(domain, CONSTANTS.REST_URLS[CONSTANTS.DEFAULT_DOMAIN])
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint
    return base + endpoint


def private_rest_url(endpoint: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """Authenticated endpoints share the same base URL as public ones on LMEX."""
    return public_rest_url(endpoint, domain)


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    time_synchronizer: Optional[TimeSynchronizer] = None,
    domain: str = CONSTANTS.DEFAULT_DOMAIN,
    time_provider: Optional[Callable] = None,
    auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (
        lambda: get_current_server_time(
            throttler=throttler,
            domain=domain,
        )
    )
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[
            TimeSynchronizerRESTPreProcessor(
                synchronizer=time_synchronizer, time_provider=time_provider
            ),
        ],
    )
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(
    throttler: AsyncThrottler,
) -> WebAssistantsFactory:
    return WebAssistantsFactory(throttler=throttler)


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None,
    domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> float:
    """
    Fetches the LMEX server time.
    Response format: {"iso": "...", "epoch": <unix seconds as float>}
    """
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    response = await rest_assistant.execute_request(
        url=public_rest_url(endpoint=CONSTANTS.SERVER_TIME_PATH_URL, domain=domain),
        method=RESTMethod.GET,
        throttler_limit_id=CONSTANTS.NETWORK_CHECK_PATH_URL,
    )
    # LMEX returns {"iso": "...", "epoch": <seconds float>}
    return float(response["epoch"])


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """Returns True if the market is active and eligible for trading."""
    return exchange_info.get("active", False) is True
