import time
from decimal import Decimal
from typing import Any, Dict

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.001"),
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"


def is_pair_information_valid(pair_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its market information

    :param pair_info: the market information for a trading pair

    :return: True if the trading pair is enabled, False otherwise
    """
    # Check if pair_info is a dictionary before calling .get()
    if not isinstance(pair_info, dict):
        return False
    
    # Must have a symbol field
    if "symbol" not in pair_info:
        return False
    
    # For AsterDex, we might need to check different fields
    # Let's be more flexible with the validation
    status = pair_info.get("statusCode") or pair_info.get("status") or pair_info.get("state")
    if status is not None:
        # Prefer Binance-style TRADING, but allow common enabled synonyms
        valid_statuses = {"TRADING", "trading", "Normal", "normal", "active", "ACTIVE", "enabled", "ENABLED", "1", 1, True}
        return status in valid_statuses
    
    # If no status field, assume it's valid if it has a symbol
    # This is more permissive for AsterDex
    return True


def get_ms_timestamp() -> int:
    return int(_time() * 1e3)


class AsterdexConfigMap(BaseConnectorConfigMap):
    connector: str = "asterdex"
    asterdex_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your AsterDex API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    asterdex_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your AsterDex secret key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="asterdex")


KEYS = AsterdexConfigMap.model_construct()


def _time():
    """
    Private function created just to have a method that can be safely patched during unit tests and make tests
    independent from real time
    """
    return time.time()
