import re
from decimal import Decimal
from typing import Any, Dict

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Bitget fees: https://www.bitget.com/en/rate?tab=1

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
    symbol = exchange_info.get("symbol")
    not_number = bool(re.match(r'^\D*$', symbol))

    return symbol is not None and not_number


class BitgetPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "bitget_perpetual"
    bitget_perpetual_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Bitget Perpetual API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )
    bitget_perpetual_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Bitget Perpetual secret key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )
    bitget_perpetual_passphrase: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Bitget Perpetual passphrase",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )
    model_config = ConfigDict(title="bitget_perpetual")


KEYS = BitgetPerpetualConfigMap.model_construct()
