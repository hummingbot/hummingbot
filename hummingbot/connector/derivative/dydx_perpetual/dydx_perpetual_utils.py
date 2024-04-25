from decimal import Decimal

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USD"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0005"),
    taker_percent_fee_decimal=Decimal("0.002"),
)


def clamp(value, minvalue, maxvalue):
    return max(minvalue, min(value, maxvalue))


class DydxPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="dydx_perpetual", client_data=None)
    dydx_perpetual_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your dydx Perpetual API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    dydx_perpetual_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your dydx Perpetual API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    dydx_perpetual_passphrase: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your dydx Perpetual API passphrase",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    dydx_perpetual_stark_private_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your stark private key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    dydx_perpetual_ethereum_address: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your ethereum wallet address",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "dydx_perpetual"


KEYS = DydxPerpetualConfigMap.construct()
