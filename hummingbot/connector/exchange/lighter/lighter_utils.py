from decimal import Decimal

from pydantic import AliasChoices, ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "ETH-USDC"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.00015"),
    taker_percent_fee_decimal=Decimal("0.0004"),
)


class LighterConfigMap(BaseConnectorConfigMap):
    connector: str = "lighter"

    lighter_api_key: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices("lighter_api_key"),
        json_schema_extra={
            "prompt": "Enter your Lighter API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    lighter_api_secret: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices("lighter_api_secret", "lighter_api_key_index"),
        json_schema_extra={
            "prompt": "Enter your Lighter API secret or API key index",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    lighter_account_index: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices("lighter_account_index"),
        json_schema_extra={
            "prompt": "Enter your Lighter account index",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    lighter_private_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("lighter_private_key", "lighter_signer_private_key", "lighter_eoa_private_key"),
        json_schema_extra={
            "prompt": "Enter your Lighter signer private key (optional for read-only; required for signed order placement/cancel)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": False,
        },
    )

    model_config = ConfigDict(title="lighter")


KEYS = LighterConfigMap.model_construct()

OTHER_DOMAINS = ["lighter_testnet"]
OTHER_DOMAINS_PARAMETER = {"lighter_testnet": "lighter_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"lighter_testnet": "ETH-USDC"}
OTHER_DOMAINS_DEFAULT_FEES = {"lighter_testnet": [0.00015, 0.0004]}


class LighterTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "lighter_testnet"

    lighter_testnet_api_key: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices("lighter_testnet_api_key"),
        json_schema_extra={
            "prompt": "Enter your Lighter testnet API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    lighter_testnet_api_secret: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices("lighter_testnet_api_secret"),
        json_schema_extra={
            "prompt": "Enter your Lighter testnet API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    lighter_testnet_account_index: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices("lighter_testnet_account_index"),
        json_schema_extra={
            "prompt": "Enter your Lighter testnet account index",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    lighter_testnet_private_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("lighter_testnet_private_key", "lighter_testnet_signer_private_key"),
        json_schema_extra={
            "prompt": "Enter your Lighter testnet signer private key (optional for read-only; required for signed order placement/cancel)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": False,
        },
    )

    model_config = ConfigDict(title="lighter_testnet")


OTHER_DOMAINS_KEYS = {
    "lighter_testnet": LighterTestnetConfigMap.model_construct(),
}
