from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True


EXAMPLE_PAIR = "BTC-USD"


DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),
    taker_percent_fee_decimal=Decimal("0.0007"),
    buy_percent_fee_deducted_from_returns=True
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    return exchange_info.get("type", None) == "spot" and exchange_info.get("enabled", False)


class FtxConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="ftx", client_data=None)
    ftx_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your FTX API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    ftx_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your FTX API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    ftx_subaccount_name: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your FTX subaccount name (if this is not a subaccount, leave blank)",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "ftx"


KEYS = FtxConfigMap.construct()
