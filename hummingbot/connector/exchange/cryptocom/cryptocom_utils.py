from decimal import Decimal
from typing import Any, Dict

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.00075"),
    taker_percent_fee_decimal=Decimal("0.00075"),
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    instrument_type = str(exchange_info.get("instrument_type", "")).upper()
    state = str(exchange_info.get("state", "")).upper()
    tradable = exchange_info.get("tradable", True)

    return instrument_type == "SPOT" and state not in {"INACTIVE", "DISABLED"} and bool(tradable)


class CryptocomConfigMap(BaseConnectorConfigMap):
    connector: str = "cryptocom"
    cryptocom_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Crypto.com Exchange API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    cryptocom_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Crypto.com Exchange API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="cryptocom")


KEYS = CryptocomConfigMap.model_construct()
