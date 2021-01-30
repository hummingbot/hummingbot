import aiohttp
from typing import Dict, Any

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange

CENTRALIZED = True

EXAMPLE_PAIR = "LRC-USDT"

DEFAULT_FEES = [0.0, 0.2]

LOOPRING_ROOT_API = "https://api3.loopring.io"
LOOPRING_WS_KEY_PATH = "/v2/ws/key"

KEYS = {
    "loopring_accountid":
        ConfigVar(key="loopring_accountid",
                  prompt="Enter your Loopring account id >>> ",
                  required_if=using_exchange("loopring"),
                  is_secure=True,
                  is_connect_key=True),
    "loopring_exchangeaddress":
        ConfigVar(key="loopring_exchangeaddress",
                  prompt="Enter the Loopring exchange address >>> ",
                  required_if=using_exchange("loopring"),
                  is_secure=True,
                  is_connect_key=True),
    "loopring_private_key":
        ConfigVar(key="loopring_private_key",
                  prompt="Enter your Loopring private key >>> ",
                  required_if=using_exchange("loopring"),
                  is_secure=True,
                  is_connect_key=True),
    "loopring_api_key":
        ConfigVar(key="loopring_api_key",
                  prompt="Enter your loopring api key >>> ",
                  required_if=using_exchange("loopring"),
                  is_secure=True,
                  is_connect_key=True)
}


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
