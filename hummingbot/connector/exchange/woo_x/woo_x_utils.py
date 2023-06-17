from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0003"),
    taker_percent_fee_decimal=Decimal("0.0003"),
    buy_percent_fee_deducted_from_returns=True
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    category, *rest = exchange_info['symbol'].split('_')

    return category == 'SPOT'


class WooXConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="woo_x", const=True, client_data=None)
    public_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Woo X public API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    secret_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Woo X secret API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    application_id: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Woo X application ID",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "woo_x"


KEYS = WooXConfigMap.construct()

OTHER_DOMAINS = ["woo_x_testnet"]
OTHER_DOMAINS_PARAMETER = {"woo_x_testnet": "woo_x_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"woo_x_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"woo_x_testnet": DEFAULT_FEES}


class WooXTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="woo_x_testnet", const=True, client_data=None)
    public_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Woo X public API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    secret_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Woo X secret API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    application_id: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Woo X application ID",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "woo_x_testnet"


OTHER_DOMAINS_KEYS = {"woo_x_testnet": WooXTestnetConfigMap.construct()}
