import typing
from dataclasses import dataclass
from typing import Optional

from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.connector.exchange.coinbase_pro import coinbase_pro_constants as CONSTANTS
from hummingbot.core.web_assistant.connections.data_types import EndpointRESTRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if typing.TYPE_CHECKING:
    from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_auth import CoinbaseProAuth

CENTRALIZED = True

EXAMPLE_PAIR = "ETH-USDC"

DEFAULT_FEES = [0.5, 0.5]

KEYS = {
    "coinbase_pro_api_key":
        ConfigVar(key="coinbase_pro_api_key",
                  prompt="Enter your Coinbase API key >>> ",
                  required_if=using_exchange("coinbase_pro"),
                  is_secure=True,
                  is_connect_key=True),
    "coinbase_pro_secret_key":
        ConfigVar(key="coinbase_pro_secret_key",
                  prompt="Enter your Coinbase secret key >>> ",
                  required_if=using_exchange("coinbase_pro"),
                  is_secure=True,
                  is_connect_key=True),
    "coinbase_pro_passphrase":
        ConfigVar(key="coinbase_pro_passphrase",
                  prompt="Enter your Coinbase passphrase >>> ",
                  required_if=using_exchange("coinbase_pro"),
                  is_secure=True,
                  is_connect_key=True),
}


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


def build_coinbase_pro_web_assistant_factory(
    auth: Optional['CoinbaseProAuth'] = None
) -> WebAssistantsFactory:
    """The web-assistant's composition root."""
    api_factory = WebAssistantsFactory(auth=auth)
    return api_factory
