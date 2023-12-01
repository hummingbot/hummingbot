from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData

EXAMPLE_PAIR = "test_usd-penumbra"


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
