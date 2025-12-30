from decimal import Decimal
from typing import Any, Dict

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Aevo fees: https://www.aevo.com/en/rate?tab=1

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.00036"),
    taker_percent_fee_decimal=Decimal("0.001"),
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information

    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    symbol = bool(exchange_info.get("symbol"))
    dated_futures = bool(exchange_info.get("deliveryPeriod"))

    return symbol and not dated_futures


class AevoPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "aevo_perpetual"
    aevo_perpetual_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Aevo Perpetual API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )
    aevo_perpetual_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Aevo Perpetual secret key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )
    aevo_perpetual_passphrase: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Aevo Perpetual passphrase",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )
    model_config = ConfigDict(title="aevo_perpetual")


KEYS = AevoPerpetualConfigMap.model_construct()
