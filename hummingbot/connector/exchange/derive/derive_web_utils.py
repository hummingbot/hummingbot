# from dataclasses import dataclass
import random
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Dict, Optional

import hummingbot.connector.exchange.derive.derive_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

MAX_INT_256 = 2**255 - 1
MIN_INT_256 = -(2**255)
MAX_INT_32 = 2**31 - 1


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
        ],
    )
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(throttler=throttler)
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


def decimal_to_big_int(value: Decimal) -> int:
    result_value = int(value * Decimal(10**18))
    if result_value < MIN_INT_256 or result_value > MAX_INT_256:
        raise ValueError(f"resulting integer value must be between {MIN_INT_256} and {MAX_INT_256}")
    return result_value


def get_action_nonce(nonce_iter: int = 0) -> int:
    """
    Used to generate a unique nonce to prevent replay attacks on-chain.

    Uses the current UTC timestamp in milliseconds and a random number up to 3 digits.

    :param nonce_iter: allows to enter a specific number between 0 and 999 unless. If None is passed a random number is chosen
    """
    if nonce_iter is None:
        nonce_iter = random.randint(0, 999)
    return int(str(utc_now_ms()) + str(nonce_iter))


def utc_now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)
