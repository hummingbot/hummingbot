from decimal import Decimal

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USD"

# Default fees: Tier 0 of the Decibel fee schedule (< $10M 30-day volume).
# Maker: 0.0110%, Taker: 0.0340%. See https://docs.decibel.trade for the full table.
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.00011"),
    taker_percent_fee_decimal=Decimal("0.00034"),
)


class DecibelPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "decibel_perpetual"

    # Decibel's API gateway (Aptos Labs) requires Authorization: Bearer <key> for ALL
    # endpoints, including /api/v1/markets and /api/v1/prices. This flag tells
    # MarketDataProvider to pass the real API keys to the non-trading connector it
    # creates for rate-source updates, instead of empty strings.
    use_auth_for_public_endpoints: bool = True

    decibel_perpetual_api_wallet_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Decibel Perpetual API Wallet Private Key (hex format, with or without 0x prefix)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )

    decibel_perpetual_main_wallet_public_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Decibel Perpetual Main Wallet Public Key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )

    decibel_perpetual_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Decibel Perpetual API Key from geomi.dev (required for all API access)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )

    decibel_perpetual_gas_station_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Decibel Perpetual Gas Station API Key from geomi.dev (required for sponsored transactions)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )

    model_config = ConfigDict(title="decibel_perpetual")


KEYS = DecibelPerpetualConfigMap.model_construct()

OTHER_DOMAINS = ["decibel_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"decibel_perpetual_testnet": "decibel_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"decibel_perpetual_testnet": "BTC-USD"}
OTHER_DOMAINS_DEFAULT_FEES = {"decibel_perpetual_testnet": [0.00011, 0.00034]}


class DecibelPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "decibel_perpetual_testnet"

    # See DecibelPerpetualConfigMap for rationale.
    use_auth_for_public_endpoints: bool = True

    decibel_perpetual_testnet_api_wallet_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Decibel Perpetual Testnet API Wallet Private Key (hex format, with or without 0x prefix)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )

    decibel_perpetual_testnet_main_wallet_public_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Decibel Perpetual Testnet Main Wallet Public Key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )

    decibel_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Decibel Perpetual Testnet API Key from geomi.dev (required)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )

    decibel_perpetual_testnet_gas_station_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Decibel Perpetual Testnet Gas Station API Key from geomi.dev (required for sponsored transactions)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )

    model_config = ConfigDict(title="decibel_perpetual_testnet")


OTHER_DOMAINS_KEYS = {
    "decibel_perpetual_testnet": DecibelPerpetualTestnetConfigMap.model_construct()
}
