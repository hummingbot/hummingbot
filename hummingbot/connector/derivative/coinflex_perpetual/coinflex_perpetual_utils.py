from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

import hummingbot.connector.derivative.coinflex_perpetual.constants as CONSTANTS
from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0000"),
    taker_percent_fee_decimal=Decimal("0.0008"),
    buy_percent_fee_deducted_from_returns=True
)


CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USD"


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
    return exchange_info.get("type", None) in ["FUTURE"] and " Perp" in exchange_info.get("name", "")


def decimal_val_or_none(string_value: str):
    return Decimal(string_value) if string_value else None


class CoinflexPerpetulConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="coinflex_perpetual", const=True, client_data=None)
    coinflex_perpetual_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Coinflex Perpetual API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    coinflex_perpetual_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Coinflex Perpetual API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "coinflex_perpetual"


KEYS = CoinflexPerpetulConfigMap.construct()


OTHER_DOMAINS = ["coinflex_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"coinflex_perpetual_testnet": "coinflex_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"coinflex_perpetual_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"coinflex_perpetual_testnet": DEFAULT_FEES}


class CoinflexPerpetulTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="coinflex_perpetual_testnet", const=True, client_data=None)
    coinflex_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Coinflex Perpetual testnet API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    coinflex_perpetual_testnet_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Coinflex Perpetual testnet API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "coinflex_perpetual_testnet"


OTHER_DOMAINS_KEYS = {"coinflex_perpetual_testnet": CoinflexPerpetulTestnetConfigMap.construct()}
