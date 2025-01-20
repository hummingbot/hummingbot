import random
import time

# from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from eth_abi.abi import encode
from web3 import Web3

import hummingbot.connector.exchange.derive.derive_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

MAX_INT_256 = 2**255 - 1
MIN_INT_256 = -(2**255)
MAX_INT_32 = 2**31 - 1


class DeriveRESTPreProcessor(RESTPreProcessorBase):

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        request.headers["Content-Type"] = (
            "application/json"
        )
        return request


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
        auth: Optional[AuthBase] = None) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[DeriveRESTPreProcessor()],
        auth=auth)
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[DeriveRESTPreProcessor()])
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
        throttler,
        domain
) -> float:
    return time.time()


def is_exchange_information_valid(rule: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information

    :param exchange_info: the exchange information for a trading pair

    :return: True if the trading pair is enabled, False otherwise
    """
    return True


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


def order_to_call(order):
    return {
        "instrument_name": order["instrument_name"],
        "direction": order["direction"],
        "order_type": order["order_type"],
        "mmp": False,
        "time_in_force": order["time_in_force"],
    }


def to_abi_encoded(order_spec):
    price = order_spec["limit_price"]
    asset_address = order_spec["asset_address"]
    sub_id = int(order_spec["sub_id"])
    limit_price = Decimal(price)
    amount = Decimal(order_spec["amount"])
    max_fee = Decimal(order_spec["max_fee"])
    recipient_id = int(order_spec["recipient_id"])
    is_bid = order_spec["is_bid"]
    return encode(
        ["address", "uint", "int", "int", "uint", "uint", "bool"],
        [
            Web3.to_checksum_address(asset_address),
            sub_id,
            decimal_to_big_int(limit_price),
            decimal_to_big_int(amount),
            decimal_to_big_int(max_fee),
            recipient_id,
            is_bid,
        ],
    )


def to_json(order):
    limit_price = order["limit_price"],
    amount = order["amount"],
    max_fee = order["max_fee"],
    return {
        "limit_price": str(limit_price),
        "amount": str(amount),
        "max_fee": str(max_fee),
    }
