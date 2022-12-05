from decimal import Decimal
from typing import Any, Dict

from pydantic import Field
from pydantic.types import SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.001"),
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information

    :param exchange_info: the exchange information for a trading pair

    :return: True if the trading pair is enabled, False otherwise
    """
    return exchange_info.get("tradesEnabled", False)


class WhitebitConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="whitebit", const=True, client_data=None)
    whitebit_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your WhiteBit API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    whitebit_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your WhiteBit secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "whitebit"


KEYS = WhitebitConfigMap.construct()
