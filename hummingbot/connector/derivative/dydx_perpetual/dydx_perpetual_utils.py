
from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

CENTRALIZED = True


EXAMPLE_PAIR = "BTC-USD"


DEFAULT_FEES = [0.05, 0.2]


def build_api_factory() -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(throttler=AsyncThrottler(rate_limits=[]))
    return api_factory


class DydxPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="dydx_perpetual", client_data=None)
    dydx_perpetual_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your dydx Perpetual API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    dydx_perpetual_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your dydx Perpetual API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    dydx_perpetual_passphrase: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your dydx Perpetual API passphrase",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    dydx_perpetual_account_number: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your dydx Perpetual API account_number",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    dydx_perpetual_stark_private_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your stark private key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    dydx_perpetual_ethereum_address: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your ethereum wallet address",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "dydx_perpetual"


KEYS = DydxPerpetualConfigMap.construct()
