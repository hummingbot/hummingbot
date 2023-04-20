from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-AUD"

# https://www.btcmarkets.net/fees
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0085"),
    taker_percent_fee_decimal=Decimal("0.0085"),
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    return exchange_info.get("status", None) in ("Online", "Post Only", "Limit Only", "Offline")


class BtcMarketsConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="btc_markets", const=True, client_data=None)
    btc_markets_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your BtcMarkets API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    btc_markets_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your BtcMarkets API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "btc_markets"


KEYS = BtcMarketsConfigMap.construct()
