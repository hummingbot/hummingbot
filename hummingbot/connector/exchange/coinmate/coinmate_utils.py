from decimal import Decimal
from typing import Any, Dict

from pydantic import ConfigDict, Field, SecretStr

import hummingbot.connector.exchange.coinmate.coinmate_constants as CONSTANTS
from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-EUR"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.003"),
    taker_percent_fee_decimal=Decimal("0.003"),
    buy_percent_fee_deducted_from_returns=True
)


class CoinmateConfigMap(BaseConnectorConfigMap):
    connector: str = "coinmate"
    
    coinmate_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your Coinmate API key (publicKey)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    
    coinmate_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your Coinmate secret key (privateKey)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    
    coinmate_client_id: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your Coinmate client ID",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    
    model_config = ConfigDict(title="coinmate")


KEYS = CoinmateConfigMap.model_construct()


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    if not isinstance(exchange_info, dict):
        return False
    
    if "data" not in exchange_info:
        return False
    
    if exchange_info.get("error", True):
        return False
        
    trading_pairs = exchange_info.get("data", [])
    return isinstance(trading_pairs, list) and len(trading_pairs) > 0

def calculate_backoff_time(retry_attempt: int) -> float:
    return CONSTANTS.INITIAL_BACKOFF_TIME * (2 ** retry_attempt)
