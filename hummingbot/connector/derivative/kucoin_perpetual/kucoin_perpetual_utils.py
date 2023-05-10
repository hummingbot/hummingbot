from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Kucoin Futures fees: https://www.kucoin.com/vip/level
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0002"),
    taker_percent_fee_decimal=Decimal("0.0006"),
    percent_fee_token="USDT")

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USD"


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information

    :param exchange_info: the exchange information for a trading pair

    :return: True if the trading pair is enabled, False otherwise
    """
    status = exchange_info.get("status")
    valid = status is not None and status in ["Open"]
    return valid


class KucoinPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="kucoin_perpetual", client_data=None)
    kucoin_perpetual_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Kucoin Perpetual API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    kucoin_perpetual_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Kucoin Perpetual secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    kucoin_perpetual_passphrase: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your KuCoin Perpetual passphrase",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "kucoin_perpetual"


KEYS = KucoinPerpetualConfigMap.construct()

OTHER_DOMAINS = ["kucoin_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"kucoin_perpetual_testnet": "kucoin_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"kucoin_perpetual_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {
    "kucoin_perpetual_testnet": TradeFeeSchema(
        maker_percent_fee_decimal=Decimal("-0.00025"),
        taker_percent_fee_decimal=Decimal("0.00075"),
    )
}


class KucoinPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="kucoin_perpetual_testnet", client_data=None)
    kucoin_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Kucoin Perpetual Testnet API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    kucoin_perpetual_testnet_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Kucoin Perpetual Testnet secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    kucoin_perpetual_testnet_passphrase: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your KuCoin Perpetual Testnet passphrase",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "kucoin_perpetual_testnet"


OTHER_DOMAINS_KEYS = {
    "kucoin_perpetual_testnet": KucoinPerpetualTestnetConfigMap.construct()
}
