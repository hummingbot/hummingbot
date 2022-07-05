from typing import Optional

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USD"
DEFAULT_FEES = [0.02, 0.07]


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> Optional[str]:
    return exchange_trading_pair.replace("PERP", "USD")


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("USD", "PERP")


class FtxPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="ftx_perpetual", client_data=None)

    ftx_perpetual_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your FTX API key",
            prompt_on_new=True,
            is_secure=True,
            is_connect_key=True,
        )
    )

    ftx_perpetual_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your FTX API secret",
            prompt_on_new=True,
            is_secure=True,
            is_connect_key=True,
        )
    )

    ftx_perpetual_subaccount_name: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your FTX subaccount name (if this is not a subaccount, leave blank)",
            prompt_on_new=True,
            is_secure=True,
            is_connect_key=True,
        )
    )

    class Config:
        title = "ftx_perpetual"


KEYS = FtxPerpetualConfigMap.construct()
