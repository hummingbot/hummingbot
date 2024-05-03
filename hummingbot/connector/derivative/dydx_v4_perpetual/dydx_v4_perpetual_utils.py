from decimal import Decimal

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USD"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0001"),
    taker_percent_fee_decimal=Decimal("0.0005"),
)


def clamp(value, minvalue, maxvalue):
    return max(minvalue, min(value, maxvalue))


class DydxV4PerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="dydx_v4_perpetual", client_data=None)
    dydx_v4_perpetual_secret_phrase: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your dydx v4 secret_phrase(24 words)",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    dydx_v4_perpetual_chain_address: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your dydx_v4 chain address ( starts with 'dydx' )",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "dydx_v4_perpetual"


KEYS = DydxV4PerpetualConfigMap.construct()
