import time
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict

from dateutil.parser import parse as dateparse
from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = False
DOMAIN = ["tegro"]
EXAMPLE_PAIR = "ZRX-ETH"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0"),
    taker_percent_fee_decimal=Decimal("0"),
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    symbol: str = exchange_info.get("symbol", "")
    state: str = exchange_info.get("state", "")
    return True if state == "verified" and symbol.count("_") == 1 else False


def get_ms_timestamp() -> int:
    return int(_time() * 1e3)


def int_val_or_none(string_value: str,
                    on_error_return_none: bool = True,
                    ) -> int:
    try:
        return int(string_value)
    except Exception:
        if on_error_return_none:
            return None
        else:
            return int('0')


def str_val_or_none(
    string_value: str,
    on_error_return_none: bool = True,
) -> int:
    try:
        return str(string_value)
    except Exception:
        if on_error_return_none:
            return None
        else:
            return int('0')


def decimal_val_or_none(string_value: str,
                        on_error_return_none: bool = True,
                        ) -> Decimal:
    try:
        return Decimal(string_value)
    except Exception:
        if on_error_return_none:
            return None
        else:
            return Decimal('0')


def datetime_val_or_now(string_value: str,
                        string_format: str = '%Y-%m-%dT%H:%M:%S.%fZ',
                        on_error_return_now: bool = True,
                        ) -> datetime:
    try:
        return datetime.strptime(string_value, string_format)
    except Exception:
        if on_error_return_now:
            return datetime.now()
        else:
            return None


def str_date_to_ts(date: str) -> int:
    return int(dateparse(date).timestamp())


class TegroConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="tegro", const=True, client_data=None)
    tegro_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Public Wallet Address",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    tegro_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Private Wallet Address",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "tegro"


KEYS = TegroConfigMap.construct()

OTHER_DOMAINS = [
    "tegro_polygon_testnet",
    "tegro_base_testnet",
    "tegro_optimism_testnet"
]
OTHER_DOMAINS_PARAMETER = {
    "tegro_polygon_testnet": "tegro_polygon_testnet",
    "tegro_base_testnet": "tegro_base_testnet",
    "tegro_optimism_testnet": "tegro_optimism_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {
    "tegro_polygon_testnet": "BTC-USDT",
    "tegro_base_testnet": "BTC-USDT",
    "tegro_optimism_testnet": "BTC-USDT"
}
OTHER_DOMAINS_DEFAULT_FEES = {
    "tegro_polygon_testnet": DEFAULT_FEES,
    "tegro_base_testnet": DEFAULT_FEES,
    "tegro_optimism_testnet": DEFAULT_FEES}


class TegroTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="tegro_optimism_testnet", const=True, client_data=None)
    tegro_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Public Wallet Address",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    tegro_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Private Wallet Address",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "tegro_optimism_testnet"


OTHER_DOMAINS_KEYS = {"tegro_polygon_testnet": TegroTestnetConfigMap.construct(),
                      "tegro_base_testnet": TegroTestnetConfigMap.construct(),
                      "tegro_optimism_testnet": TegroTestnetConfigMap.construct()}


def _time():
    """
    Private function created just to have a method that can be safely patched during unit tests and make tests
    independent from real time
    """
    return time.time()
