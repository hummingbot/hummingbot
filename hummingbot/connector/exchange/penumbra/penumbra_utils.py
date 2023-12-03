from typing import Any, Dict, Optional

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.connector.exchange.penumbra.penumbra_constants import RATE_LIMITS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

EXAMPLE_PAIR = "gm-gn"


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(throttler=throttler, auth=auth)
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(RATE_LIMITS)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information

    :param exchange_info: the exchange information for a trading pair

    :return: True if the trading pair is enabled, False otherwise
    """

    return exchange_info.get("instType", None) == "SPOT"


class PenumbraConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="penumbra", client_data=None)

    pclientd_url: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your pclientd url (e.g. localhost:8081)",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ))

    class Config:
        title = "penumbra"


KEYS = PenumbraConfigMap.construct()
