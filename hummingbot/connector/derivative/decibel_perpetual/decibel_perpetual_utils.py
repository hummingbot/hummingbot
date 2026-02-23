from decimal import Decimal
from typing import Any, Dict

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0"),
    taker_percent_fee_decimal=Decimal("0"),
)

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USD"


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    # Decibel markets contain a 'mode' field (Open/ReduceOnly/CloseOnly)
    return str(exchange_info.get("mode", "open")).lower() in ("open", "reduceonly", "closeonly")


class DecibelPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "decibel_perpetual"

    decibel_perpetual_bearer_token: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Decibel Bearer token (from Geomi)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    decibel_perpetual_origin: str = Field(
        default="https://app.decibel.trade",
        json_schema_extra={
            "prompt": "Enter your application Origin header value",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    decibel_perpetual_account_address: str = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Decibel Trading Account address",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    model_config = ConfigDict(title="decibel_perpetual")


KEYS = DecibelPerpetualConfigMap.model_construct()
