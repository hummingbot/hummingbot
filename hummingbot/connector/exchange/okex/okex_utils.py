import zlib
from decimal import Decimal

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0008"),
    taker_percent_fee_decimal=Decimal("0.0001"),
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"


class OkexConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="okex", client_data=None)
    okex_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your OKEx API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    okex_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your OKEx secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    okex_passphrase: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your OKEx passphrase key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "okex"


KEYS = OkexConfigMap.construct()


def inflate(data):
    """decrypts the OKEx data.
    Copied from OKEx SDK: https://github.com/okex/V3-Open-API-SDK/blob/d8becc67af047726c66d9a9b29d99e99c595c4f7/okex-python-sdk-api/websocket_example.py#L46"""
    decompress = zlib.decompressobj(-zlib.MAX_WBITS)
    inflated = decompress.decompress(data)
    inflated += decompress._flush()
    return inflated.decode('utf-8')
