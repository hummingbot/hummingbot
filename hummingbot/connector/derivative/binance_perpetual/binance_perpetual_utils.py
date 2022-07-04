import os
import socket
from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),
    taker_percent_fee_decimal=Decimal("0.0004"),
    buy_percent_fee_deducted_from_returns=True
)


CENTRALIZED = True


EXAMPLE_PAIR = "BTC-USDT"


BROKER_ID = "x-3QreWesy"


def get_client_order_id(order_side: str, trading_pair: object):
    nonce = get_tracking_nonce()
    symbols: str = trading_pair.split("-")
    base: str = symbols[0].upper()
    quote: str = symbols[1].upper()
    base_str = f"{base[0]}{base[-1]}"
    quote_str = f"{quote[0]}{quote[-1]}"
    client_instance_id = hex(abs(hash(f"{socket.gethostname()}{os.getpid()}")))[2:6]
    return f"{BROKER_ID}-{order_side.upper()[0]}{base_str}{quote_str}{client_instance_id}{nonce}"


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    return exchange_info.get("status", None) == "TRADING"


class BinancePerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="binance_perpetual", client_data=None)
    binance_perpetual_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Binance Perpetual API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    binance_perpetual_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Binance Perpetual API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )


KEYS = BinancePerpetualConfigMap.construct()

OTHER_DOMAINS = ["binance_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"binance_perpetual_testnet": "binance_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"binance_perpetual_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"binance_perpetual_testnet": [0.02, 0.04]}


class BinancePerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="binance_perpetual_testnet", client_data=None)
    binance_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Binance Perpetual testnet API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    binance_perpetual_testnet_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Binance Perpetual testnet API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "binance_perpetual"


OTHER_DOMAINS_KEYS = {"binance_perpetual_testnet": BinancePerpetualTestnetConfigMap.construct()}
