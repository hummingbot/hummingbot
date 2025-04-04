from decimal import Decimal
from typing import Any, Dict

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Kucoin Futures fees: https://www.kucoin.com/vip/level
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),
    taker_percent_fee_decimal=Decimal("0.0006"),
    percent_fee_token="USDT")

CENTRALIZED = True

EXAMPLE_PAIR = "XBT-USDT"


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information

    :param exchange_info: the exchange information for a trading pair

    :return: True if the trading pair is enabled, False otherwise
    """
    status = exchange_info.get("status")
    valid = status is not None and status in ["Open"]
    return valid


class KucoinPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "kucoin_perpetual"
    kucoin_perpetual_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Kucoin Perpetual API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    kucoin_perpetual_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Kucoin Perpetual API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    kucoin_perpetual_passphrase: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Kucoin Perpetual passphrase",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="kucoin_perpetual")


KEYS = KucoinPerpetualConfigMap.model_construct()
