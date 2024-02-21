import time
from typing import Optional

import hummingbot.connector.exchange.kraken.kraken_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
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
