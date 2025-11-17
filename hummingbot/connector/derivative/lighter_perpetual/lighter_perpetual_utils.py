from decimal import Decimal
from typing import Optional

from pydantic import ConfigDict, Field, SecretStr, field_validator

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0"),
    taker_percent_fee_decimal=Decimal("0.0002"),
    buy_percent_fee_deducted_from_returns=True,
)

CENTRALIZED = False

EXAMPLE_PAIR = "BTC-USD"

BROKER_ID = "HBOT"


def validate_bool(value: str) -> Optional[str]:
    valid_values = ("true", "yes", "y", "false", "no", "n")
    if value.lower() not in valid_values:
        return f"Invalid value, please choose value from {valid_values}"


class LighterPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "lighter_perpetual"
    lighter_perpetual_api_key_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Lighter API private key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    lighter_perpetual_account_index: int = Field(
        default=0,
        json_schema_extra={
            "prompt": "Enter your Lighter account index",
            "prompt_on_new": True,
        },
    )
    lighter_perpetual_api_key_index: int = Field(
        default=0,
        json_schema_extra={
            "prompt": "Enter your Lighter API key index",
            "prompt_on_new": True,
        },
    )
    lighter_perpetual_eth_private_key: SecretStr = Field(
        default=None,
        json_schema_extra={
            "prompt": "Enter your L1 wallet private key (optional, required for withdrawals)",
            "is_secure": True,
            "prompt_on_new": False,
        },
    )
    lighter_perpetual_domain: str = Field(
        default="mainnet",
        json_schema_extra={
            "prompt": "Enter trading domain (mainnet/testnet)",
            "prompt_on_new": True,
        },
    )

    @classmethod
    def validate_bool(cls, value: str) -> bool:
        error = validate_bool(value)
        if error:
            raise ValueError(error)
        return True

    @field_validator("lighter_perpetual_domain", mode="before")
    @classmethod
    def validate_domain(cls, v: str):
        allowed = {"mainnet", "testnet"}
        if v not in allowed:
            raise ValueError(f"Invalid domain '{v}'. Choose from {allowed}.")
        return v


KEYS = LighterPerpetualConfigMap.model_construct()

OTHER_DOMAINS = ["lighter_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"lighter_perpetual_testnet": "lighter_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"lighter_perpetual_testnet": "BTC-USD"}
OTHER_DOMAINS_DEFAULT_FEES = {"lighter_perpetual_testnet": [0, 0.0002]}


class LighterPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "lighter_perpetual_testnet"
    lighter_perpetual_testnet_api_key_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Lighter testnet API private key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    lighter_perpetual_testnet_account_index: int = Field(
        default=0,
        json_schema_extra={
            "prompt": "Enter your Lighter testnet account index",
            "prompt_on_new": True,
        },
    )
    lighter_perpetual_testnet_api_key_index: int = Field(
        default=0,
        json_schema_extra={
            "prompt": "Enter your Lighter testnet API key index",
            "prompt_on_new": True,
        },
    )
    lighter_perpetual_testnet_eth_private_key: SecretStr = Field(
        default=None,
        json_schema_extra={
            "prompt": "Enter your L1 wallet private key (optional, required for withdrawals)",
            "is_secure": True,
            "prompt_on_new": False,
        },
    )
    lighter_perpetual_testnet_domain: str = Field(
        default="testnet",
        json_schema_extra={
            "prompt": "Enter trading domain (testnet)",
            "prompt_on_new": True,
        },
    )
    model_config = ConfigDict(title="lighter_perpetual")

    @classmethod
    def validate_bool(cls, value: str) -> bool:
        error = validate_bool(value)
        if error:
            raise ValueError(error)
        return True

    @field_validator("lighter_perpetual_testnet_domain", mode="before")
    @classmethod
    def validate_domain(cls, v: str):
        allowed = {"testnet"}
        if v not in allowed:
            raise ValueError(f"Invalid domain '{v}'. Choose from {allowed}.")
        return v


OTHER_DOMAINS_KEYS = {
    "lighter_perpetual_testnet": LighterPerpetualTestnetConfigMap.model_construct()
}
