import time
from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.001"),
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"


def is_pair_information_valid(pair_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its market information

    :param pair_info: the market information for a trading pair

    :return: True if the trading pair is enabled, False otherwise
    """
    return pair_info.get("statusCode") == "Normal"


def get_ms_timestamp() -> int:
    return int(_time() * 1e3)


class AscendExConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="ascend_ex", client_data=None)
    ascend_ex_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your AscendEx API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    ascend_ex_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your AscendEx secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    ascend_ex_group_id: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your AscendEx group Id",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "ascend_ex"


KEYS = AscendExConfigMap.construct()


def _time():
    """
    Private function created just to have a method that can be safely patched during unit tests and make tests
    independent from real time
    """
    return time.time()
