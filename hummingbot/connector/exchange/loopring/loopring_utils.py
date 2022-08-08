from typing import Any, Dict

import aiohttp
from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData

CENTRALIZED = True

EXAMPLE_PAIR = "LRC-USDT"

DEFAULT_FEES = [0.0, 0.2]

LOOPRING_ROOT_API = "https://api3.loopring.io"
LOOPRING_WS_KEY_PATH = "/v2/ws/key"


class LoopringConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="loopring", client_data=None)
    loopring_accountid: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Loopring account id",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    loopring_exchangeaddress: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter the Loopring exchange address",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    loopring_private_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Loopring private key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    loopring_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your loopring api key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "loopring"


KEYS = LoopringConfigMap.construct()


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    # loopring returns trading pairs in the correct format natively
    return exchange_trading_pair


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    # loopring expects trading pairs in the same format as hummingbot internally represents them
    return hb_trading_pair


async def get_ws_api_key():
    async with aiohttp.ClientSession() as client:
        response: aiohttp.ClientResponse = await client.get(
            f"{LOOPRING_ROOT_API}{LOOPRING_WS_KEY_PATH}"
        )
        if response.status != 200:
            raise IOError(f"Error getting WS key. Server responded with status: {response.status}.")

        response_dict: Dict[str, Any] = await response.json()
        return response_dict['data']
