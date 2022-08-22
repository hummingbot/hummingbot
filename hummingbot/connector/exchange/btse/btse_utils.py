from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "ZRX-ETH"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.001"),
    buy_percent_fee_deducted_from_returns=True
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    return exchange_info.get("active", False)


class BtseConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="btse", const=True, client_data=None)
    btse_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Btse API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    btse_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Btse API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "btse"


KEYS = BtseConfigMap.construct()

# OTHER_DOMAINS = ["btse_us"]
# OTHER_DOMAINS_PARAMETER = {"btse_us": "us"}
# OTHER_DOMAINS_EXAMPLE_PAIR = {"btse_us": "BTC-USDT"}
# OTHER_DOMAINS_DEFAULT_FEES = {"btse_us": DEFAULT_FEES}


# class BtseUSConfigMap(BaseConnectorConfigMap):
#     connector: str = Field(default="btse_us", const=True, client_data=None)
#     btse_api_key: SecretStr = Field(
#         default=...,
#         client_data=ClientFieldData(
#             prompt=lambda cm: "Enter your Btse US API key",
#             is_secure=True,
#             is_connect_key=True,
#             prompt_on_new=True,
#         )
#     )
#     btse_api_secret: SecretStr = Field(
#         default=...,
#         client_data=ClientFieldData(
#             prompt=lambda cm: "Enter your Btse US API secret",
#             is_secure=True,
#             is_connect_key=True,
#             prompt_on_new=True,
#         )
#     )

#     class Config:
#         title = "btse_us"


# OTHER_DOMAINS_KEYS = {"btse_us": BtseUSConfigMap.construct()}
