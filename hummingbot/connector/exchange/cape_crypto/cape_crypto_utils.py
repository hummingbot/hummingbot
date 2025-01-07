from datetime import datetime
import math
from decimal import Decimal
from enum import Enum, auto
from typing import Any, Dict, List

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce, get_tracking_nonce_low_res

from . import cape_crypto_constants as CONSTANTS

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-ZAR"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("-0.01"),
    taker_percent_fee_decimal=Decimal("0.1"),
    buy_percent_fee_deducted_from_returns=False
)

class CapeCryptoConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="cape_crypto", client_data=None)
    cape_crypto_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Cape Crypto API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    cape_crypto_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Cape Crypto secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "cape_crypto"


KEYS = CapeCryptoConfigMap.construct()

def convert_from_exchange_trading_pair_basic(exchange_trading_pair: str) -> str:
    return exchange_trading_pair[:3] + '-' + exchange_trading_pair[3:]


def convert_from_exchange_trading_pair_with_lookup(exchange_trading_pair: str, exchange_trading_pairs: List[str]) -> str:
    for pair in exchange_trading_pairs:
        matching_pair = convert_to_exchange_trading_pair(pair)
        if matching_pair == exchange_trading_pair:\
            return pair
    return exchange_trading_pair[:3] + '-' + exchange_trading_pair[3:]


def convert_from_exchange_trading_pair(short_name: str) -> str:
    return short_name.replace("/", "-")


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "").lower()


def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    side = "B" if is_buy else "S"
    return f"{CONSTANTS.HBOT_ORDER_ID_PREFIX}{side}-{trading_pair}-{get_tracking_nonce()}"

def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    return exchange_info.get("state", None) == 'enabled'


def get_api_reason(code: str) -> str:
    return CONSTANTS.API_REASONS.get(int(code), code)


def get_rest_url(path_url: str) -> str:
    return f"{CONSTANTS.REST_URL}{CONSTANTS.REST_VERSION}{path_url}"


def get_path_url(rest_url: str) -> str:
    return rest_url.split(CONSTANTS.REST_URL)[1]


def get_wss_url(path_url: str) -> str:
    return f"{CONSTANTS.WSS_URL}{path_url}"


def get_base_currency(currency_pair: str) -> str:
    return currency_pair[:3]


# get timestamp in milliseconds
def get_ms_timestamp() -> int:
    return get_tracking_nonce_low_res()


# convert milliseconds timestamp to seconds
def ms_timestamp_to_s(ms: int) -> int:
    return math.floor(ms / 1e3)


# convert exchange timestamp to epoch
def convert_exchange_timestamp_to_ms(timestamp: str) -> int:
    timestamp_formatted = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return int(timestamp_formatted.timestamp() * 1000)


class OrderType(Enum):
    TAKER = auto()
    MAKER = auto()
  