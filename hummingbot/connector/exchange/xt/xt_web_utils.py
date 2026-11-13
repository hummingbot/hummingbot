from typing import Any, Callable, Dict, Optional

import hummingbot.connector.exchange.xt.xt_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

DEFINITIVE_ORDER_CREATE_REJECTION_CODES = frozenset(
    {
        CONSTANTS.TIMESTAMP_ERROR_CODE,
        "ORDER_001", "ORDER_002", "ORDER_003", "ORDER_006", "ORDER_007", "ORDER_008",
        "ORDER_F0101", "ORDER_F0102", "ORDER_F0103", "ORDER_F0201", "ORDER_F0202", "ORDER_F0203",
        "ORDER_F0301", "ORDER_F0401", "ORDER_F0501", "ORDER_F0502", "ORDER_F0503", "ORDER_F0504",
        "SYMBOL_001", "SYMBOL_002", "SYMBOL_003", "SYMBOL_004", "SYMBOL_005", "SYMBOL_010", "SYMBOL_011",
        "AUTH_001", "AUTH_002", "AUTH_003", "AUTH_004", "AUTH_005", "AUTH_006", "AUTH_007",
        "AUTH_101", "AUTH_102", "AUTH_103", "AUTH_104", "AUTH_106",
    }
)


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return f"{CONSTANTS.REST_URL}{path_url}"


def private_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return f"{CONSTANTS.REST_URL}{path_url}"


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    time_synchronizer: Optional[TimeSynchronizer] = None,
    domain: str = CONSTANTS.DEFAULT_DOMAIN,
    time_provider: Optional[Callable] = None,
    auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time(throttler=throttler, domain=domain))
    return WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[TimeSynchronizerRESTPreProcessor(
            synchronizer=time_synchronizer, time_provider=time_provider,
        )],
    )


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    return WebAssistantsFactory(throttler=throttler)


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
    result = result_from_response(response, "server time")
    return float(result["serverTime"])


def result_from_response(response: Dict[str, Any], context: str) -> Any:
    if not isinstance(response, dict):
        raise IOError(f"XT {context} returned a non-JSON response: {response}")

    response_code = response.get("rc")
    response_message = response.get("mc")
    if response_code != CONSTANTS.XT_SUCCESS_CODE:
        raise IOError(f"XT {context} failed: rc={response_code} mc={response_message} response={response}")

    return response.get("result")


def is_time_sync_error_response(response: Any) -> bool:
    """Recognize XT's application-level timestamp denial.

    XT may encode private API failures in an HTTP-success JSON envelope. That
    bypasses Hummingbot's transport-level time-synchronizer retry unless the
    connector inspects ``rc`` itself.
    """

    return (
        isinstance(response, dict)
        and response.get("rc") != 0
        and response.get("mc") == CONSTANTS.TIMESTAMP_ERROR_CODE
    )


def is_definitive_order_create_rejection(response: Any) -> bool:
    """Whether XT's response proves the POST did not create an order.

    All other sent create outcomes stay uncertain and must settle by exact
    authenticated venue evidence before the executor can retry.
    """

    return (
        isinstance(response, dict)
        and response.get("rc") != 0
        and response.get("mc") in DEFINITIVE_ORDER_CREATE_REJECTION_CODES
    )
