from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "ZRX-ETH"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.1"),
    taker_percent_fee_decimal=Decimal("0.2")
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    return exchange_info.get("trading") == "Enabled"


class BitstampConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="bitstamp", const=True, client_data=None)
    bitstamp_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Bitstamp API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    bitstamp_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Bitstamp API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "bitstamp"


KEYS = BitstampConfigMap.construct()
