from typing import Optional

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.connector.exchange.ndax import ndax_constants as CONSTANTS
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-CAD"
HUMMINGBOT_ID_PREFIX = 777

# NDAX fees: https://ndax.io/fees
# Fees have to be expressed as percent value
DEFAULT_FEES = [0.2, 0.2]


# USE_ETHEREUM_WALLET not required because default value is false
# FEE_TYPE not required because default value is Percentage
# FEE_TOKEN not required because the fee is not flat


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "")


def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    ts_micro_sec: int = get_tracking_nonce()
    return f"{HUMMINGBOT_ID_PREFIX}{ts_micro_sec}"


def rest_api_url(connector_variant_label: Optional[str]) -> str:
    variant = connector_variant_label if connector_variant_label else "ndax_main"
    return CONSTANTS.REST_URLS.get(variant)


def wss_url(connector_variant_label: Optional[str]) -> str:
    variant = connector_variant_label if connector_variant_label else "ndax_main"
    return CONSTANTS.WSS_URLS.get(variant)


class NdaxConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="ndax", client_data=None)
    ndax_uid: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your NDAX user ID (uid)",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    ndax_account_name: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter the name of the account you want to use",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    ndax_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your NDAX API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    ndax_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your NDAX secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "ndax"


KEYS = NdaxConfigMap.construct()

OTHER_DOMAINS = ["ndax_testnet"]
OTHER_DOMAINS_PARAMETER = {"ndax_testnet": "ndax_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"ndax_testnet": "BTC-CAD"}
OTHER_DOMAINS_DEFAULT_FEES = {"ndax_testnet": [0.2, 0.2]}


class NdaxTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="ndax_testnet", client_data=None)
    ndax_testnet_uid: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your NDAX Testnet user ID (uid)",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    ndax_testnet_account_name: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter the name of the account you want to use",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    ndax_testnet_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your NDAX Testnet API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    ndax_testnet_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your NDAX Testnet secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "ndax_testnet"


OTHER_DOMAINS_KEYS = {"ndax_testnet": NdaxTestnetConfigMap.construct()}
