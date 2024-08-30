from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import (
    BaseConnectorConfigMap,
    ClientFieldData,
)
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True

EXAMPLE_PAIR = "ETH-USDT"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.001"),
)


def is_pair_information_valid(pair_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its market information

    :param pair_info: the market information for a trading pair

    :return: True if the trading pair is enabled, False otherwise
    """
    return pair_info.get("enableTrading", False)


class NobitexConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="nobitex", client_data=None)
    nobitex_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your nobitex API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    nobitex_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your nobitex secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    nobitex_passphrase: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your nobitex passphrase",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "nobitex"


KEYS = NobitexConfigMap.construct()

OTHER_DOMAINS = ["nobitex_hft"]
OTHER_DOMAINS_PARAMETER = {"nobitex_hft": "hft"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"nobitex_hft": "ETH-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"nobitex_hft": DEFAULT_FEES}


class NobitexHFTConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="nobitex_hft", client_data=None)
    nobitex_hft_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your nobitex HFT API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    nobitex_hft_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your nobitex HFT secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    nobitex_hft_passphrase: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your nobitex HFT passphrase",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "nobitex_hft"


OTHER_DOMAINS_KEYS = {"nobitex_hft": NobitexHFTConfigMap.construct()}
