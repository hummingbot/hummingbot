from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.connector.derivative.phemex_perpetual import phemex_perpetual_constants as CONSTANTS
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    percent_fee_token=CONSTANTS.COLLATERAL_TOKEN,
    maker_percent_fee_decimal=Decimal("0.0001"),
    taker_percent_fee_decimal=Decimal("0.0006"),
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    status = exchange_info.get("status")
    valid = status == "Listed"
    return valid


class PhemexPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="phemex_perpetual", client_data=None)
    phemex_perpetual_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Phemex Perpetual API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    phemex_perpetual_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Phemex Perpetual API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )


KEYS = PhemexPerpetualConfigMap.construct()

OTHER_DOMAINS = ["phemex_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"phemex_perpetual_testnet": "phemex_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"phemex_perpetual_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"phemex_perpetual_testnet": [0.01, 0.06]}


class PhemexPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="phemex_perpetual_testnet", client_data=None)
    phemex_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Phemex Perpetual testnet API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    phemex_perpetual_testnet_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Phemex Perpetual testnet API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "phemex_perpetual"


OTHER_DOMAINS_KEYS = {"phemex_perpetual_testnet": PhemexPerpetualTestnetConfigMap.construct()}
