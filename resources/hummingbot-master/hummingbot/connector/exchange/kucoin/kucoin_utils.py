from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
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


class KuCoinConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="kucoin", client_data=None)
    kucoin_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your KuCoin API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    kucoin_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your KuCoin secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    kucoin_passphrase: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your KuCoin passphrase",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "kucoin"


KEYS = KuCoinConfigMap.construct()

OTHER_DOMAINS = ["kucoin_hft"]
OTHER_DOMAINS_PARAMETER = {"kucoin_hft": "hft"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"kucoin_hft": "ETH-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"kucoin_hft": DEFAULT_FEES}


class KuCoinHFTConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="kucoin_hft", client_data=None)
    kucoin_hft_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your KuCoin HFT API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    kucoin_hft_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your KuCoin HFT secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    kucoin_hft_passphrase: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your KuCoin HFT passphrase",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "kucoin_hft"


OTHER_DOMAINS_KEYS = {"kucoin_hft": KuCoinHFTConfigMap.construct()}
