from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

import hummingbot.connector.exchange.derive.derive_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def private_rest_url(*args, **kwargs) -> str:
    return rest_url(*args, **kwargs)


def public_rest_url(*args, **kwargs) -> str:
    return rest_url(*args, **kwargs)


def rest_url(path_url: str, domain: str = "derive"):
    base_url = CONSTANTS.BASE_URL if domain == "derive" else CONSTANTS.TESTNET_BASE_URL
    return base_url + path_url


def wss_url(domain: str = "derive"):
    base_ws_url = CONSTANTS.WSS_URL if domain == "derive" else CONSTANTS.TESTNET_WSS_URL
    return base_ws_url


class DeriveRESTPreProcessor(RESTPreProcessorBase):
    """
    Stamps every REST request with a User-Agent.

    v3 rejects requests that arrive without one, and public calls do not pass through the auth
    layer that would otherwise add it.
    """

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        request.headers = request.headers or {}
        request.headers.setdefault("User-Agent", CONSTANTS.USER_AGENT)
        request.headers.setdefault("Content-Type", "application/json")
        return request


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
            DeriveRESTPreProcessor(),
            TimeSynchronizerRESTPreProcessor(synchronizer=time_synchronizer, time_provider=time_provider),
        ],
    )
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(throttler=throttler, rest_pre_processors=[DeriveRESTPreProcessor()])
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> float:
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    response = await rest_assistant.execute_request(
        url=public_rest_url(path_url=CONSTANTS.SERVER_TIME_PATH_URL, domain=domain),
        method=RESTMethod.GET,
        throttler_limit_id=CONSTANTS.SERVER_TIME_PATH_URL,
    )
    server_time = response["result"]
    return server_time


def is_exchange_information_valid(rule: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information

    :param exchange_info: the exchange information for a trading pair

    :return: True if the trading pair is enabled, False otherwise
    """
    return True


def order_to_call(order):
    return {
        "instrument_name": order["instrument_name"],
        "direction": order["direction"],
        "order_type": order["order_type"],
        "referral_code": order["referral_code"],
        "mmp": False,
        "time_in_force": order["time_in_force"],
        "label": order["label"]
    }


def utc_now_ms() -> int:
    """
    Current UTC time in milliseconds.

    Used for websocket request ids and the login timestamp. The signing helpers, including the
    nanosecond action nonce, live in derive_common_utils.
    """
    return int(datetime.now(timezone.utc).timestamp() * 1000)
