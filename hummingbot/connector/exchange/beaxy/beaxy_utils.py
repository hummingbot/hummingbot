# -*- coding: utf-8 -*-
from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData

CENTRALIZED = True

EXAMPLE_PAIR = 'BTC-USDC'

DEFAULT_FEES = [0.15, 0.25]


class BeaxyConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="beaxy", client_data=None)
    beaxy_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Beaxy API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    beaxy_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Beaxy secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "beaxy"


KEYS = BeaxyConfigMap.construct()
