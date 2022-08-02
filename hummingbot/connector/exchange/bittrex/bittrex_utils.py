from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"


DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0035"),
    taker_percent_fee_decimal=Decimal("0.0035"),
)


class BittrexConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="bittrex", const=True, client_data=None)
    bittrex_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Bittrex API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    bittrex_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Bittrex secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )


KEYS = BittrexConfigMap.construct()


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    if exchange_info.get("status") == "ONLINE":
        return True
    return False
