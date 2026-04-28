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
    Gemini returns status "open" for active pairs. Perpetual swaps share base/quote with
    their spot counterparts (e.g. AVAXGUSD vs AVAXGUSDPERP), so we restrict to product_type "spot".
    """
    return (
        exchange_info.get("status", "") == "open"
        and exchange_info.get("product_type", "") == "spot"
    )


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

OTHER_DOMAINS = ["gemini_sandbox"]
OTHER_DOMAINS_PARAMETER = {"gemini_sandbox": "gemini_sandbox"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"gemini_sandbox": "BTC-USD"}
OTHER_DOMAINS_DEFAULT_FEES = {"gemini_sandbox": DEFAULT_FEES}


class GeminiSandboxConfigMap(BaseConnectorConfigMap):
    connector: str = "gemini_sandbox"
    gemini_sandbox_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your Gemini Sandbox API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    gemini_sandbox_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your Gemini Sandbox API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="gemini_sandbox")


OTHER_DOMAINS_KEYS = {"gemini_sandbox": GeminiSandboxConfigMap.model_construct()}
