from decimal import Decimal
from typing import Any, Dict, Optional

from pydantic import ConfigDict, Field, SecretStr, field_validator

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
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
    if isinstance(exchange_info, dict):
        symbol: str = exchange_info.get("symbol", "")
        state: str = exchange_info.get("state", "")
        return True if state == "verified" and symbol.count("_") == 1 else False


def validate_mainnet_exchange(value: str) -> Optional[str]:
    """
    Permissively interpret a string as a boolean
    """
    valid_values = ('base')
    if value.lower() not in valid_values:
        return f"Invalid value, please choose value from {valid_values}"


def validate_testnet_exchange(value: str) -> Optional[str]:
    """
    Permissively interpret a string as a boolean
    """
    valid_values = ('base', 'polygon', 'optimism')
    if value.lower() not in valid_values:
        return f"Invalid value, please choose value from {valid_values}"


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


class TegroConfigMap(BaseConnectorConfigMap):
    connector: str = "tegro"
    tegro_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Public Wallet Address",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    tegro_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Private Wallet Address",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    chain_name: str = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your preferred chain. (base/ )",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )

    @field_validator("chain_name", mode="before")
    @classmethod
    def validate_exchange(cls, v: str):
        """Used for client-friendly error output."""
        if isinstance(v, str):
            ret = validate_mainnet_exchange(v)
            if ret is not None:
                raise ValueError(ret)
        return v
    model_config = ConfigDict(title="tegro")


KEYS = TegroConfigMap.model_construct()


class TegroTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "tegro_testnet"
    tegro_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Public Wallet Address",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    tegro_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Private Wallet Address",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    chain_name: str = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your preferred chain. (base/polygon/optimism)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )

    @field_validator("chain_name", mode="before")
    @classmethod
    def validate_exchange(cls, v: str):
        """Used for client-friendly error output."""
        if isinstance(v, str):
            ret = validate_testnet_exchange(v)
            if ret is not None:
                raise ValueError(ret)
        return v
    model_config = ConfigDict(title="tegro_testnet")


OTHER_DOMAINS = ["tegro_testnet"]
OTHER_DOMAINS_PARAMETER = {"tegro_testnet": "tegro_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"tegro_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"tegro_testnet": DEFAULT_FEES}
OTHER_DOMAINS_KEYS = {"tegro_testnet": TegroTestnetConfigMap.model_construct()}
