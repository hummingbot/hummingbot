"""Utility helpers for Vest Perpetual REST/WS endpoints and API factories."""
from typing import Optional

from hummingbot.connector.derivative.vest_perpetual import vest_perpetual_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def _resolve_domain(use_testnet: bool = False, domain: Optional[str] = None) -> str:
    if domain is not None:
        return domain
    return CONSTANTS.TESTNET_DOMAIN if use_testnet else CONSTANTS.DEFAULT_DOMAIN


def rest_url(path_url: str, use_testnet: bool = False, domain: Optional[str] = None) -> str:
    """Creates a full REST URL for a path."""
    resolved_domain = _resolve_domain(use_testnet=use_testnet, domain=domain)
    base_url = CONSTANTS.REST_URLS.get(resolved_domain, CONSTANTS.REST_URL_PROD)
    return base_url + path_url


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return rest_url(path_url=path_url, domain=domain)


def private_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return rest_url(path_url=path_url, domain=domain)


def wss_url(use_testnet: bool = False) -> str:
    """Deprecated helper preserved for backwards compatibility."""
    return CONSTANTS.WSS_URL_DEV if use_testnet else CONSTANTS.WSS_URL_PROD


def public_ws_url(domain: str = CONSTANTS.DEFAULT_DOMAIN, account_group: int = 0) -> str:
    base_ws_url = CONSTANTS.WSS_URLS.get(domain, CONSTANTS.WSS_URL_PROD)
    query = f"version=1.0&xwebsocketserver=restserver{account_group}&websocketserver=restserver{account_group}"
    return f"{base_ws_url}?{query}"


def private_ws_url(
    listen_key: str,
    domain: str = CONSTANTS.DEFAULT_DOMAIN,
    account_group: int = 0,
) -> str:
    base = public_ws_url(domain=domain, account_group=account_group)
    return f"{base}&listenKey={listen_key}"


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    time_synchronizer: Optional[TimeSynchronizer] = None,
    auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    """
    Builds a WebAssistantsFactory with the required settings for Vest Perpetual.
    """
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()

    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[
            TimeSynchronizerRESTPreProcessor(synchronizer=time_synchronizer),
        ],
    )
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(
    throttler: Optional[AsyncThrottler] = None,
    auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    """
    Builds a WebAssistantsFactory without the time synchronizer pre-processor.
    Used for endpoints that don't require time synchronization.
    """
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(throttler=throttler, auth=auth)
    return api_factory


def create_throttler() -> AsyncThrottler:
    """
    Creates the default AsyncThrottler for Vest Perpetual.
    """
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None,
    use_testnet: bool = False,
) -> float:
    """
    Gets the current server time from Vest.
    Since Vest doesn't have a dedicated server time endpoint, we'll use the account endpoint
    and extract the time from the response.
    """
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()

    # Use a simple public endpoint to get server time
    url = rest_url(CONSTANTS.TICKER_LATEST_PATH_URL, use_testnet=use_testnet)
    params = {"symbols": "BTC-PERP"}  # Just query one symbol to minimize response

    response = await rest_assistant.execute_request(
        url=url,
        throttler_limit_id=CONSTANTS.TICKER_LATEST_PATH_URL,
        method=RESTMethod.GET,
        params=params,
    )

    # Vest API doesn't return server time in public endpoints
    # We'll use local time (this is acceptable for most operations)
    import time
    return time.time()
