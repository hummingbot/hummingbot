from decimal import Decimal

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),  # Extended default maker fee: 0.02%
    taker_percent_fee_decimal=Decimal("0.0005"),  # Extended default taker fee: 0.05%
    buy_percent_fee_deducted_from_returns=True
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDC"


class ExtendedPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "extended_perpetual"
    extended_perpetual_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Extended API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    extended_perpetual_stark_public_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Extended Stark public key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    extended_perpetual_stark_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Extended Stark private key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )


KEYS = ExtendedPerpetualConfigMap.model_construct()

