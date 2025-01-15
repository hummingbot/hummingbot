import logging
import time
from typing import Optional, Dict

import hummingbot.connector.exchange.kraken.kraken_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def private_rest_url(*args, **kwargs) -> str:
    return rest_url(*args, **kwargs)


def public_rest_url(*args, **kwargs) -> str:
    return rest_url(*args, **kwargs)


def rest_url(path_url: str, domain: str = "kraken"):
    base_url = CONSTANTS.BASE_URL
    return base_url + path_url


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        auth: Optional[AuthBase] = None, ) -> WebAssistantsFactory:
    throttler = throttler
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth
    )
    return api_factory


def is_exchange_information_valid(trading_pair_details) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information

    :param exchange_info: the exchange information for a trading pair

    :return: True if the trading pair is enabled, False otherwise
    Want to filter out dark pool trading pairs from the list of trading pairs
    For more info, please check
    https://support.kraken.com/hc/en-us/articles/360001391906-Introducing-the-Kraken-Dark-Pool
    """
    if trading_pair_details.get('altname'):
        return not trading_pair_details.get('altname').endswith('.d')
    return True


async def get_current_server_time(
        throttler,
        domain
) -> float:
    return time.time()


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.PUBLIC_API_LIMITS)


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    return WebAssistantsFactory(throttler=throttler)


async def get_current_server_time_s(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> float:
    """
    Get the current server time in seconds
    :param throttler: the throttler to use for the request
    :param domain: the coinbase_advanced_trade domain to connect to ("com" or "us"). The default value is "com"
    :return: the current server time in seconds
    """
    """
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getservertime
    """
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    response: Dict = await rest_assistant.execute_request(
        url=private_rest_url(path_url=CONSTANTS.TIME_PATH_URL, domain=domain),
        method=RESTMethod.GET,
        throttler_limit_id=CONSTANTS.TIME_PATH_URL,
    )
    server_time: float = float(response["result"]["unixtime"])

    return server_time


async def get_current_server_time_ms(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> int:
    server_time_s = await get_current_server_time_s(throttler=throttler, domain=domain)
    return int(server_time_s * 1000)
