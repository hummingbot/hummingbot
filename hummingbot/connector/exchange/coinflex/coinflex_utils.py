from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

import hummingbot.connector.exchange.coinflex.coinflex_constants as CONSTANTS
from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USD"
DEFAULT_FEES = [0.0, 0.08]


def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    """
    Creates a client order id for a new order
    :param is_buy: True if the order is a buy order, False otherwise
    :param trading_pair: the trading pair the order will be operating with
    :return: an identifier for the new order to be used in the client
    """
    side = "0" if is_buy else "1"
    return f"{CONSTANTS.HBOT_ORDER_ID_PREFIX}{side}{get_tracking_nonce()}"


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    return exchange_info.get("type", None) == "SPOT"


def decimal_val_or_none(string_value: str):
    return Decimal(string_value) if string_value else None


class CoinflexConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="coinflex", client_data=None)
    coinflex_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your CoinFLEX API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    coinflex_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your CoinFLEX API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "coinflex"


KEYS = CoinflexConfigMap.construct()

OTHER_DOMAINS = ["coinflex_test"]
OTHER_DOMAINS_PARAMETER = {"coinflex_test": "coinflex_test"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"coinflex_test": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"coinflex_test": [0.1, 0.1]}


class CoinflexTestConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="coinflex_test", client_data=None)
    coinflex_test_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your CoinFLEX Staging API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    coinflex_test_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your CoinFLEX Staging API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "coinflex_test"


OTHER_DOMAINS_KEYS = {"coinflex_test": CoinflexTestConfigMap.construct()}
