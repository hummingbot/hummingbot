from decimal import Decimal

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0"),
    taker_percent_fee_decimal=Decimal("0"),
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"


class EveConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="eve", const=True, client_data=None)
    eve_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your EVE API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    eve_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your EVE secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    eve_user_id: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your EVE user ID",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "eve"


KEYS = EveConfigMap.construct()
