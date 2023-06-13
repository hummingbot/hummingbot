from typing import Callable, Optional, Union

import hummingbot.connector.exchange.coinbase_advanced_trade.cat_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v2_response_types import (
    CoinbaseAdvancedTradeTimeResponse,
)
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided public REST endpoint
    :param path_url: a public REST endpoint
    :param domain: the coinbase_advanced_trade domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    if path_url in CONSTANTS.SIGNIN_ENDPOINTS:
        return CONSTANTS.SIGNIN_URL.format(domain=domain) + path_url
    return CONSTANTS.REST_URL.format(domain=domain) + path_url


def private_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided private REST endpoint
    :param path_url: a private REST endpoint
    :param domain: the coinbase_advanced_trade domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    if any((path_url.startswith(p) for p in CONSTANTS.SIGNIN_ENDPOINTS)):
        return CONSTANTS.SIGNIN_URL.format(domain=domain) + path_url
    return CONSTANTS.REST_URL.format(domain=domain) + path_url


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        time_synchronizer: Optional[TimeSynchronizer] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        time_provider: Optional[Callable] = None,
        auth: Optional[AuthBase] = None, ) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time_s(
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


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(throttler=throttler)
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time_s(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> int:
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    response: CoinbaseAdvancedTradeTimeResponse = await rest_assistant.execute_request(
        url=public_rest_url(path_url=CONSTANTS.SERVER_TIME_EP, domain=domain),
        method=RESTMethod.GET,
        throttler_limit_id=CONSTANTS.SERVER_TIME_EP,
    )
    server_time: int = int(get_timestamp_from_exchange_time(response["data"]["iso"], "s"))
    return server_time


async def get_current_server_time_ms(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> int:
    server_time_s = await get_current_server_time_s(throttler=throttler, domain=domain)
    return server_time_s * 1000


async def get_current_server_time(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> int:
    server_time_s = await get_current_server_time_s(throttler=throttler, domain=domain)
    return server_time_s * 1000


def get_timestamp_from_exchange_time(exchange_time: str, unit: str) -> float:
    from datetime import datetime
    exchange_time_with_tz: str = exchange_time.replace("Z", "+00:00")

    # Oddly some time (at least in the doc) are not ISO8601 compliant with too many decimals
    # So we truncate the string to make it ISO8601 compliant
    if len(exchange_time_with_tz) > 33:
        exchange_time_truncated = exchange_time_with_tz[:26] + exchange_time_with_tz[-6:]
    else:
        exchange_time_truncated = exchange_time_with_tz
    t_s: float = datetime.fromisoformat(exchange_time_truncated).timestamp()
    if unit == "s" or unit in ("second", "seconds"):
        return t_s
    elif unit == "ms" or unit in ("millisecond", "milliseconds"):
        return t_s * 1000
    else:
        raise ValueError(f"Unsupported time unit {unit}")


def set_exchange_time_from_timestamp(timestamp: Union[int, float], timestamp_unit: str = "s") -> str:
    if timestamp_unit == "ms" or timestamp_unit in ("millisecond", "milliseconds"):
        timestamp: float = timestamp / 1000
    elif timestamp_unit == "s" or timestamp_unit in ("second", "seconds"):
        pass
    else:
        raise ValueError(f"Unsupported timestamp unit {timestamp_unit}")

    from datetime import datetime
    return datetime.utcfromtimestamp(timestamp).isoformat() + "Z"
