from decimal import Decimal

from pydantic import AliasChoices, ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USD"

# Default fee values aligned with the currently observed base tier.
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.00015"),
    taker_percent_fee_decimal=Decimal("0.0004"),
)


class LighterPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "lighter_perpetual"

    lighter_perpetual_api_key: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices(
            "lighter_perpetual_api_key",
            "lighter_api_key",
        ),
        json_schema_extra={
            "prompt": "Enter your Lighter API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )

    lighter_perpetual_api_secret: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices(
            "lighter_perpetual_api_secret",
            "lighter_api_secret",
            "lighter_perpetual_api_key_index",
            "lighter_api_key_index",
        ),
        json_schema_extra={
            "prompt": "Enter your Lighter API secret or API key index",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )

    lighter_perpetual_account_index: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices(
            "lighter_perpetual_account_index",
            "lighter_account_index",
        ),
        json_schema_extra={
            "prompt": "Enter your Lighter account index",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )

    lighter_perpetual_private_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices(
            "lighter_perpetual_private_key",
            "lighter_private_key",
            "lighter_signer_private_key",
            "lighter_eoa_private_key",
        ),
        json_schema_extra={
            "prompt": "Enter your Lighter signer private key (optional for data streams/read-only; required for signed order placement/cancel)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": False
        }
    )

    model_config = ConfigDict(title="lighter_perpetual")


KEYS = LighterPerpetualConfigMap.model_construct()

OTHER_DOMAINS = ["lighter_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"lighter_perpetual_testnet": "lighter_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"lighter_perpetual_testnet": "BTC-USD"}
OTHER_DOMAINS_DEFAULT_FEES = {"lighter_perpetual_testnet": [0.00015, 0.0004]}


class LighterPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "lighter_perpetual_testnet"

    lighter_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices(
            "lighter_perpetual_testnet_api_key",
            "lighter_testnet_api_key",
        ),
        json_schema_extra={
            "prompt": "Enter your Lighter testnet API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )

    lighter_perpetual_testnet_api_secret: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices(
            "lighter_perpetual_testnet_api_secret",
            "lighter_testnet_api_secret",
        ),
        json_schema_extra={
            "prompt": "Enter your Lighter testnet API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )

    lighter_perpetual_testnet_account_index: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices(
            "lighter_perpetual_testnet_account_index",
            "lighter_testnet_account_index",
        ),
        json_schema_extra={
            "prompt": "Enter your Lighter testnet account index",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )

    lighter_perpetual_testnet_private_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices(
            "lighter_perpetual_testnet_private_key",
            "lighter_testnet_private_key",
            "lighter_testnet_signer_private_key",
            "lighter_testnet_eoa_private_key",
        ),
        json_schema_extra={
            "prompt": "Enter your Lighter testnet signer private key (optional for data streams/read-only; required for signed order placement/cancel)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": False
        }
    )

    model_config = ConfigDict(title="lighter_perpetual_testnet")


OTHER_DOMAINS_KEYS = {
    "lighter_perpetual_testnet": LighterPerpetualTestnetConfigMap.model_construct()
}

