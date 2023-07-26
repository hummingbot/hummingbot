import re
from typing import Callable, Dict, NamedTuple, Optional, Tuple, Union

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

from . import coinbase_advanced_trade_v2_constants as constants


def public_rest_url(path_url: str, domain: str = constants.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided public REST endpoint
    :param path_url: a public REST endpoint
    :param domain: the Coinbase Advanced Trade domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    if path_url in constants.SIGNIN_ENDPOINTS:
        return constants.SIGNIN_URL.format(domain=domain) + path_url

    return constants.REST_URL.format(domain=domain) + path_url


def private_rest_url(path_url: str, domain: str = constants.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided private REST endpoint
    :param path_url: a private REST endpoint
    :param domain: the coinbase_advanced_trade_v2 domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    if any((path_url.startswith(p) for p in constants.SIGNIN_ENDPOINTS)):
        return constants.SIGNIN_URL.format(domain=domain) + path_url

    return constants.REST_URL.format(domain=domain) + path_url


def endpoint_from_url(path_url: str, domain: str = constants.DEFAULT_DOMAIN) -> str:
    """
    Recreates the endpoint from the url
    :param path_url: URL to the endpoint
    :param domain: the coinbase_advanced_trade_v2 domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    if domain not in path_url:
        raise ValueError(f"The domain {domain} is not part of the provided URL {path_url}")

    endpoint: str = re.split(domain, path_url)[1]

    # Must start with '/'
    if not endpoint.startswith("/"):
        endpoint = f"/{endpoint}"

    return endpoint


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        time_synchronizer: Optional[TimeSynchronizer] = None,
        domain: str = constants.DEFAULT_DOMAIN,
        time_provider: Optional[Callable] = None,
        auth: Optional[AuthBase] = None, ) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time_s(
        throttler=throttler,
        domain=domain,
    ))
    return WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[
            TimeSynchronizerRESTPreProcessor(
                synchronizer=time_synchronizer, time_provider=time_provider
            ),
        ],
    )


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    return WebAssistantsFactory(throttler=throttler)


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(constants.RATE_LIMITS)


async def get_current_server_time_s(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = constants.DEFAULT_DOMAIN,
) -> float:
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    response: Dict = await rest_assistant.execute_request(
        url=public_rest_url(path_url=constants.SERVER_TIME_EP, domain=domain),
        method=RESTMethod.GET,
        throttler_limit_id=constants.SERVER_TIME_EP,
    )
    server_time: float = float(get_timestamp_from_exchange_time(response["data"]["iso"], "s"))
    return server_time


# Ok, forgot HB does not like units on time ...
async def get_current_server_time(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = constants.DEFAULT_DOMAIN,
) -> float:
    return await get_current_server_time_s(throttler=throttler, domain=domain)


async def get_current_server_time_ms(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = constants.DEFAULT_DOMAIN,
) -> int:
    server_time_s = await get_current_server_time_s(throttler=throttler, domain=domain)
    return int(server_time_s * 1000)


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
    if unit in {"s", "second", "seconds"}:
        return t_s
    elif unit in {"ms", "millisecond", "milliseconds"}:
        return t_s * 1000
    else:
        raise ValueError(f"Unsupported time unit {unit}")


def set_exchange_time_from_timestamp(timestamp: Union[int, float], timestamp_unit: str = "s") -> str:
    if timestamp_unit in {"ms", "millisecond", "milliseconds"}:
        timestamp /= 1000
    elif timestamp_unit not in ("s", "second", "seconds"):
        raise ValueError(f"Unsupported timestamp unit {timestamp_unit}")

    from datetime import datetime
    return f"{datetime.utcfromtimestamp(timestamp).isoformat()}Z"


def pair_to_symbol(pair: str) -> str:
    return pair


def symbol_to_pair(symbol: str) -> str:
    return symbol


class CoinbaseAdvancedTradeWSSMessage(NamedTuple):
    """
    Coinbase Advanced Trade Websocket API message
    https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-channels
    ```json
    {
      "channel": "market_trades",
      "client_id": "",
      "timestamp": "2023-02-09T20:19:35.39625135Z",
      "sequence_num": 0,
      "events": [
        ...
      ]
    }
    ```
    """

    channel: str
    client_id: str
    timestamp: str
    sequence_num: int
    events: Tuple