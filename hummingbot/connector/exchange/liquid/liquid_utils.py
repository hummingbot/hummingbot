from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData

CENTRALIZED = True

EXAMPLE_PAIR = "ETH-USD"

DEFAULT_FEES = [0.1, 0.1]


class LiquidConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="liquid", client_data=None)
    liquid_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Liquid API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    liquid_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Liquid secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "liquid"


KEYS = LiquidConfigMap.construct()
