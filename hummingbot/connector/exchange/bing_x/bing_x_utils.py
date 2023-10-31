
from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from typing import Any, Dict
from pydantic import Field, SecretStr
from hummingbot.core.data_type.trade_fee import TradeFeeSchema
from decimal import Decimal

CENTRALIZED = True
EXAMPLE_PAIR = "AURA-USDT"
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.001"),
    buy_percent_fee_deducted_from_returns=True
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    return exchange_info.get("showStatus") is True


class BingXConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="bing_x", client_data=None)
    bingx_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your BingX API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    bingx_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your BingX secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "bing_x"


KEYS = BingXConfigMap.construct()
