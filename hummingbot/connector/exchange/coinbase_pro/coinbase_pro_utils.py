import typing
from dataclasses import dataclass
from typing import Optional

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.connector.exchange.coinbase_pro import coinbase_pro_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.connections.data_types import EndpointRESTRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if typing.TYPE_CHECKING:
    from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_auth import CoinbaseProAuth

CENTRALIZED = True

EXAMPLE_PAIR = "ETH-USDC"

DEFAULT_FEES = [0.5, 0.5]


class CoinbaseProConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="coinbase_pro", client_data=None)
    coinbase_pro_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Coinbase API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    coinbase_pro_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Coinbase secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    coinbase_pro_passphrase: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Coinbase passphrase",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "coinbase_pro"


KEYS = CoinbaseProConfigMap.construct()


@dataclass
class CoinbaseProRESTRequest(EndpointRESTRequest):
    def __post_init__(self):
        super().__post_init__()
        self._ensure_endpoint_for_auth()

    @property
    def base_url(self) -> str:
        return CONSTANTS.REST_URL

    def _ensure_endpoint_for_auth(self):
        if self.is_auth_required and self.endpoint is None:
            raise ValueError("The endpoint must be specified if authentication is required.")


def build_coinbase_pro_web_assistant_factory(auth: Optional['CoinbaseProAuth'] = None) -> WebAssistantsFactory:
    """The web-assistant's composition root."""
    throttler = AsyncThrottler(rate_limits=[])
    api_factory = WebAssistantsFactory(throttler=throttler, auth=auth)
    return api_factory
