from decimal import Decimal
from typing import Optional

from pydantic import ConfigDict, Field, SecretStr, field_validator

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0"),
    taker_percent_fee_decimal=Decimal("0"),
    buy_percent_fee_deducted_from_returns=False,
)

CENTRALIZED = False
EXAMPLE_PAIR = "ETH-USDC"


def validate_non_negative_int(value) -> int:
    if value in (None, ""):
        return None
    ivalue = int(value)
    if ivalue < 0:
        raise ValueError("Value must be non-negative.")
    return ivalue


class LighterConfigMap(BaseConnectorConfigMap):
    connector: str = "lighter"
    lighter_l1_address: str = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Lighter L1 wallet address",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    lighter_account_index: Optional[int] = Field(
        default=None,
        json_schema_extra={
            "prompt": "Enter your Lighter account index (leave blank to use the main account for your L1 address)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    lighter_api_key_index: int = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Lighter API key index",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    lighter_api_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Lighter API private key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    lighter_account_limit: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Lighter account limit(Standard/Premium/Plus/Builder)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
            "default_value": "Standard",
        },
    )
    model_config = ConfigDict(title="lighter")

    @field_validator("lighter_account_index", "lighter_api_key_index", mode="before")
    @classmethod
    def validate_indexes(cls, value):
        return validate_non_negative_int(value)


KEYS = LighterConfigMap.model_construct()

OTHER_DOMAINS = ["lighter_testnet"]
OTHER_DOMAINS_PARAMETER = {"lighter_testnet": "lighter_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"lighter_testnet": EXAMPLE_PAIR}
OTHER_DOMAINS_DEFAULT_FEES = {"lighter_testnet": DEFAULT_FEES}


class LighterTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "lighter_testnet"
    lighter_testnet_l1_address: str = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Lighter Testnet L1 wallet address",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    lighter_testnet_account_index: Optional[int] = Field(
        default=None,
        json_schema_extra={
            "prompt": "Enter your Lighter Testnet account index (leave blank to use the main account for your L1 address)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    lighter_testnet_api_key_index: int = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Lighter Testnet API key index",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    lighter_testnet_api_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Lighter Testnet API private key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    lighter_testnet_account_limit: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Lighter Testnet account limit(Standard)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    model_config = ConfigDict(title="lighter_testnet")

    @field_validator("lighter_testnet_account_index", "lighter_testnet_api_key_index", mode="before")
    @classmethod
    def validate_indexes(cls, value):
        return validate_non_negative_int(value)


OTHER_DOMAINS_KEYS = {"lighter_testnet": LighterTestnetConfigMap.model_construct()}
