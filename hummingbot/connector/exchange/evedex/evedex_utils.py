from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Default trading fees for EVEDEX
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.00015"),  # 0.015% maker fee
    taker_percent_fee_decimal=Decimal("0.00045"),  # 0.045% taker fee
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"


class EvedexConfigMap(BaseConnectorConfigMap):
    """
    Configuration map for EVEDEX connector.
    This defines the required API credentials and connection parameters.
    """
    connector: str = "evedex"
    evedex_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your EVEDEX API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    evedex_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your EVEDEX secret key (used for request signatures)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    evedex_access_token: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your EVEDEX access token (Bearer token)",
            "is_secure": True,
            "prompt_on_new": True,
        }
    )
    evedex_chain_id: str = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter the chain ID used for order signatures (e.g. 8453)",
            "prompt_on_new": True,
        }
    )

    class Config:
        title = "evedex"


KEYS = EvedexConfigMap.model_construct()


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information.

    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    trading_status = exchange_info.get("trading")
    market_state = exchange_info.get("marketState")
    base_info = (exchange_info.get("from") or {}).get("symbol")
    quote_info = (exchange_info.get("to") or {}).get("symbol")

    return all([
        trading_status in {"all", "restricted"},
        market_state not in {"CLOSED", "HALTED"},
        base_info is not None,
        quote_info is not None,
    ])
