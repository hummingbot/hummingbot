from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.000"),
    taker_percent_fee_decimal=Decimal("0.000"),
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    return exchange_info.get("status") == "TRADING"


class HashkeyGlobalConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="hashkey", const=True, client_data=None)
    hashkey_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Hashkey Global API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    hashkey_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Hashkey Global API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "hashkey"


KEYS = HashkeyGlobalConfigMap.construct()

OTHER_DOMAINS = ["hashkey_global_testnet"]
OTHER_DOMAINS_PARAMETER = {
    "hashkey_global_testnet": "hashkey_global_testnet",
}
OTHER_DOMAINS_EXAMPLE_PAIR = {
    "hashkey_global_testnet": "BTC-USDT",
}
OTHER_DOMAINS_DEFAULT_FEES = {
    "hashkey_global_testnet": DEFAULT_FEES,
}


class HashkeyGlobalTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="hashkey_global_testnet", const=True, client_data=None)
    hashkey_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Hashkey Global API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    hashkey_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Hashkey Global API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "hashkey_global_testnet"


OTHER_DOMAINS_KEYS = {
    "hashkey_global_testnet": HashkeyGlobalTestnetConfigMap.construct(),
}
