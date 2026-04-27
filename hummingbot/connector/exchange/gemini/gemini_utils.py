from decimal import Decimal
from typing import Any, Dict

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USD"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.0035"),
    buy_percent_fee_deducted_from_returns=False
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information.
    Gemini returns status "open" for active pairs.
    """
    status = exchange_info.get("status", "")
    return status == "open"


class GeminiConfigMap(BaseConnectorConfigMap):
    connector: str = "gemini"
    gemini_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your Gemini API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    gemini_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your Gemini API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="gemini")


KEYS = GeminiConfigMap.model_construct()
