from decimal import Decimal

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),
    taker_percent_fee_decimal=Decimal("0.0005"),
    buy_percent_fee_deducted_from_returns=True,
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USD"

BROKER_ID = "HBOT"


class DecibelPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "decibel_perpetual"
    decibel_perpetual_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Decibel API key (Bearer token from https://geomi.dev)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    decibel_perpetual_account_address: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Aptos wallet address (0x...)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    decibel_perpetual_subaccount_address: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Decibel trading subaccount address (0x...)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    decibel_perpetual_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Aptos Ed25519 private key for signing transactions",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    model_config = ConfigDict(title="decibel_perpetual")


KEYS = DecibelPerpetualConfigMap.model_construct()

OTHER_DOMAINS = ["decibel_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"decibel_perpetual_testnet": "decibel_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"decibel_perpetual_testnet": "BTC-USD"}
OTHER_DOMAINS_DEFAULT_FEES = {"decibel_perpetual_testnet": [0.02, 0.05]}


class DecibelPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "decibel_perpetual_testnet"
    decibel_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Decibel testnet API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    decibel_perpetual_testnet_account_address: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Aptos testnet wallet address (0x...)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    decibel_perpetual_testnet_subaccount_address: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Decibel testnet subaccount address (0x...)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    decibel_perpetual_testnet_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Aptos testnet Ed25519 private key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    model_config = ConfigDict(title="decibel_perpetual_testnet")


OTHER_DOMAINS_KEYS = {
    "decibel_perpetual_testnet": DecibelPerpetualTestnetConfigMap.model_construct()
}
