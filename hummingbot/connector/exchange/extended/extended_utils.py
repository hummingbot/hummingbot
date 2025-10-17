import time
from decimal import Decimal
from typing import Any, Dict

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),  # Extended default maker fee: 0.02%
    taker_percent_fee_decimal=Decimal("0.0005"),  # Extended default taker fee: 0.05%
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDC"


def is_pair_information_valid(pair_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its market information

    :param pair_info: the market information for a trading pair

    :return: True if the trading pair is enabled, False otherwise
    """
    # Check if pair_info is a dictionary before calling .get()
    if not isinstance(pair_info, dict):
        return False
    
    # Must have a symbol or market_id field
    if "symbol" not in pair_info and "market_id" not in pair_info:
        return False
    
    # Check status field - Extended uses "active" status
    status = pair_info.get("status") or pair_info.get("state")
    if status is not None:
        valid_statuses = {"active", "ACTIVE", "trading", "TRADING", "enabled", "ENABLED", "open", "OPEN"}
        return status in valid_statuses
    
    # If no status field, assume it's valid if it has a symbol/market_id
    return True


def get_ms_timestamp() -> int:
    return int(_time() * 1e3)


class ExtendedConfigMap(BaseConnectorConfigMap):
    connector: str = "extended"
    extended_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Extended API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    extended_stark_public_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Extended Stark public key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    extended_stark_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Extended Stark private key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="extended")


KEYS = ExtendedConfigMap.model_construct()


def _time():
    """
    Private function created just to have a method that can be safely patched during unit tests and make tests
    independent from real time
    """
    return time.time()

