from typing import Any, Dict

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap

EXAMPLE_PAIR = "test_usd/penumbra"


class PenumbraConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="penumbra", const=True, client_data=None)


KEYS = PenumbraConfigMap.construct()


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information

    :param exchange_info: the exchange information for a trading pair

    :return: True if the trading pair is enabled, False otherwise
    """
    return exchange_info.get("instType", None) == "SPOT"
