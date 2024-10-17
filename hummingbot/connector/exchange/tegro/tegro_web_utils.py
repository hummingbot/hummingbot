import time
from typing import Callable, Optional

import hummingbot.connector.exchange.tegro.tegro_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_rest_url(path_url: str, domain: str = "tegro"):
    base_url = CONSTANTS.TEGRO_BASE_URL if domain == "tegro" else CONSTANTS.TESTNET_BASE_URL
    return base_url + path_url


def private_rest_url(path_url: str, domain: str = "tegro"):
    base_url = CONSTANTS.TEGRO_BASE_URL if domain == "tegro" else CONSTANTS.TESTNET_BASE_URL
    return base_url + path_url


def wss_url(endpoint: str, domain: str = "tegro"):
    base_ws_url = CONSTANTS.TEGRO_WS_URL if domain == "tegro" else CONSTANTS.TESTNET_WS_URL
    return base_ws_url + endpoint


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        time_synchronizer: Optional[TimeSynchronizer] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        time_provider: Optional[Callable] = None,
        auth: Optional[AuthBase] = None, ) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time(
        throttler=throttler,
        domain=domain,
    ))
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[
            TimeSynchronizerRESTPreProcessor(synchronizer=time_synchronizer, time_provider=time_provider),
        ])
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None,

    domain=CONSTANTS.DEFAULT_DOMAIN,
) -> float:
    throttler = throttler or create_throttler()
    server_time = time.time()
    return server_time
