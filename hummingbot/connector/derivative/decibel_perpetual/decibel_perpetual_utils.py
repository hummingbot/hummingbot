from decimal import Decimal
from typing import Any, Dict

from pydantic import ConfigDict, Field, SecretStr

import hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_constants as CONSTANTS
from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),   # 0.02% maker
    taker_percent_fee_decimal=Decimal("0.0005"),   # 0.05% taker
)

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USD"


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """Check if a market is active and tradeable."""
    return exchange_info.get("status", "").lower() in ("active", "online", "trading")


class DecibelPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "decibel_perpetual"
    decibel_perpetual_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Decibel Perpetual API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    decibel_perpetual_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Decibel Perpetual API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    model_config = ConfigDict(title="decibel_perpetual")


KEYS = DecibelPerpetualConfigMap.model_construct()
