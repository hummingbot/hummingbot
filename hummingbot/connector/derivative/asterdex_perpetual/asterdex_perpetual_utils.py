from decimal import Decimal
from typing import Optional

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Default fees for AsterDex Perpetual
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),  # 0.02%
    taker_percent_fee_decimal=Decimal("0.0004"),   # 0.04%
    buy_percent_fee_deducted_from_returns=True
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"

BROKER_ID = "HBOT"


def validate_bool(value: str) -> Optional[str]:
    """Used for client-friendly error output."""
    valid_values = ["yes", "no", "y", "n", "true", "false", "1", "0"]
    if value.lower() not in valid_values:
        return f"Invalid value, please choose value from {valid_values}"

    return None


class AsterdexPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "asterdex_perpetual"
    asterdex_perpetual_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your AsterDex API secret key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    asterdex_perpetual_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your AsterDex API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )


KEYS = AsterdexPerpetualConfigMap.model_construct()
