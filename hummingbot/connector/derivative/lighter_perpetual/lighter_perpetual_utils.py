from decimal import Decimal

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.00002"),  # Lighter default maker fee: 0.002% (0.2 bps)
    taker_percent_fee_decimal=Decimal("0.0002"),  # Lighter default taker fee: 0.02% (2 bps)
    buy_percent_fee_deducted_from_returns=True
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDC"


class LighterPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "lighter_perpetual"
    lighter_perpetual_public_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Lighter Public Key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    lighter_perpetual_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Lighter Private Key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    lighter_perpetual_api_key_index: int = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Lighter API Key Index",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )


KEYS = LighterPerpetualConfigMap.model_construct()

