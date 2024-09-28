from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData

CENTRALIZED = True


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    is_spot = False
    is_trading = False

    if exchange_info.get("status", None) == "TRADING":
        is_trading = True

    permissions_sets = exchange_info.get("permissionSets", list())
    for permission_set in permissions_sets:
        # PermissionSet is a list, find if in this list we have "SPOT" value or not
        if "SPOT" in permission_set:
            is_spot = True
            break

    return is_trading and is_spot


class coincheckConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="coincheck", const=True, client_data=None)
    coincheck_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your coincheck API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    coincheck_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your coincheck API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "coincheck"


KEYS = coincheckConfigMap.construct()


class coincheckUSConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="coincheck_us", const=True, client_data=None)
    coincheck_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your coincheck US API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    coincheck_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your coincheck US API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "coincheck_us"


OTHER_DOMAINS_KEYS = {"coincheck_us": coincheckUSConfigMap.construct()}
