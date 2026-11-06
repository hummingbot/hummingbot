from email.utils import parsedate_to_datetime
from typing import Callable, Optional

import hummingbot.connector.exchange.gemini.gemini_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_rest_url(path_url: str, domain: str = "") -> str:
    return CONSTANTS.REST_URL + path_url


def private_rest_url(path_url: str, domain: str = "") -> str:
    return CONSTANTS.REST_URL + path_url


def wss_url(snapshot: Optional[int] = None) -> str:
    if snapshot is None:
        return CONSTANTS.WSS_URL
    return f"{CONSTANTS.WSS_URL}?snapshot={snapshot}"


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        time_synchronizer: Optional[TimeSynchronizer] = None,
        time_provider: Optional[Callable] = None,
        auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time(throttler=throttler))
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[
            TimeSynchronizerRESTPreProcessor(synchronizer=time_synchronizer, time_provider=time_provider),
        ])
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(throttler=throttler)
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = "",
) -> float:
    """Fetch server time (epoch milliseconds) from the Date header of a Gemini API response.

    Gemini has no server-time endpoint, so the HTTP Date header of the public symbols
    endpoint is used instead. This keeps nonces valid even when the local clock
    (e.g. a Podman VM) drifts. Failures propagate to the caller; TimeSynchronizer
    already logs them and falls back to the local clock when it has no samples.
    """
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    response = await rest_assistant.execute_request_and_get_response(
        url=public_rest_url(path_url=CONSTANTS.SYMBOLS_PATH_URL, domain=domain),
        method=RESTMethod.GET,
        throttler_limit_id=CONSTANTS.SYMBOLS_PATH_URL,
    )
    date_str = response.headers.get("Date") if response.headers is not None else None
    if not date_str:
        raise IOError("Gemini server time response is missing the Date header")
    return parsedate_to_datetime(date_str).timestamp() * 1e3
