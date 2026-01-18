from decimal import Decimal
from typing import Any, Dict

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Aevo fees: https://www.aevo.com/en/rate?tab=1

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.001"),
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information

    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    symbol = bool(exchange_info.get("symbol"))

    return symbol


class AevoConfigMap(BaseConnectorConfigMap):
    connector: str = "aevo"
    aevo_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Aevo API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    aevo_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Aevo secret key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    aevo_passphrase: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Aevo passphrase",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="aevo")


KEYS = AevoConfigMap.model_construct()
