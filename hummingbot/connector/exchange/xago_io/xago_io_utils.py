import math
from decimal import Decimal
from typing import Any, Dict, List

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce, get_tracking_nonce_low_res

from . import xago_io_constants as CONSTANTS

CENTRALIZED = True

EXAMPLE_PAIR = "XRP-ZAR"

DEFAULT_FEES = [0.25, 0.25]

HBOT_BROKER_ID = "XAGO-"


# deeply merge two dictionaries
def merge_dicts(source: Dict, destination: Dict) -> Dict:
    for key, value in source.items():
        if isinstance(value, dict):
            # get node or create one
            node = destination.setdefault(key, {})
            merge_dicts(value, node)
        else:
            destination[key] = value

    return destination


# join paths
def join_paths(*paths: List[str]) -> str:
    return "/".join(paths)


# get timestamp in milliseconds
def get_ms_timestamp() -> int:
    return get_tracking_nonce_low_res()


# convert milliseconds timestamp to seconds
def ms_timestamp_to_s(ms: int) -> int:
    return math.floor(ms / 1e3)


# Request ID class
class RequestId:
    """
    Generate request ids
    """
    _request_id: int = 0

    @classmethod
    def generate_request_id(cls) -> int:
        return get_tracking_nonce()


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    return exchange_trading_pair.replace("/", "-")


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "/")


def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    side = "B" if is_buy else "S"
    return f"{CONSTANTS.HBOT_ORDER_ID_PREFIX}{side}-{get_tracking_nonce()}"


def get_api_reason(code: str) -> str:
    return CONSTANTS.API_REASONS.get(int(code), code)


def get_rest_url(base_url: str, path_url: str) -> str:
    return f"{base_url}{path_url}"


def get_base_quote_currencies(currency_pair: str):
    currencies = currency_pair.split('-')
    return {"base": currencies[0], "quote": currencies[1]}


def get_currency_code(currency_pair: str, direction: str) -> str:
    currencies = currency_pair.split('-')
    return currencies[0] if direction == 'SELL' else currencies[1]


def get_execute_amount(amount: Decimal, price: Decimal, direction: str):
    return float(amount) * float(price) if direction == 'BUY' else float(amount)


def format_exchange_order_type(order):
    order_split = order['orderType'].split(" - ", 2)
    del order['orderType']
    order["side"] = order_split[0].lower()
    order["type"] = order_split[1].lower()
    return order


def format_exchange_trade_id(exchange_trade_id):
    trade_id = exchange_trade_id.split(":")[1]
    return trade_id

def is_exchange_information_valid(market: Dict[str, Any]) -> bool:
    if market.get("activeStatus", None) == True:
        return True
    return False

class XagoIoConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="xago_io", client_data=None)
    xago_io_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Xago API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    xago_io_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Xago secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "xago_io"


KEYS = XagoIoConfigMap.construct()
