from typing import Optional

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange

CENTRALIZED = False

USE_ETHEREUM_WALLET = False

EXAMPLE_PAIR = "IDEX-ETH"

DEFAULT_FEES = [0.1, 0.2]


EXCHANGE_NAME = "idex"

IDEX_BLOCKCHAINS = ('ETH', 'BSC')

# API Feed adjusted to sandbox url
IDEX_REST_URL_FMT = "https://api-sandbox-{blockchain}.idex.io/"
# WS Feed adjusted to sandbox url
IDEX_WS_FEED_FMT = "wss://websocket-sandbox-{blockchain}.idex.io/v1"


def validate_idex_contract_blockchain(value: str) -> Optional[str]:
    if value not in IDEX_BLOCKCHAINS:
        return f'Value {value} must be one of: {IDEX_BLOCKCHAINS}'

KEYS = {
    "idex_api_key":
        ConfigVar(key="idex_api_key",
                  prompt="Enter your IDEX API key >>> ",
                  required_if=using_exchange(EXCHANGE_NAME),
                  is_secure=True,
                  is_connect_key=True),
    "idex_api_secret_key":
        ConfigVar(key="idex_api_secret_key",
                  prompt="Enter your IDEX API secret key>>> ",
                  required_if=using_exchange(EXCHANGE_NAME),
                  is_secure=True,
                  is_connect_key=True),
    "idex_wallet_private_key":
        ConfigVar(key="idex_wallet_private_key",
                  prompt="Enter your wallet private key>>> ",
                  required_if=using_exchange(EXCHANGE_NAME),
                  is_secure=True,
                  is_connect_key=True),
    "idex_contract_blockchain":
        ConfigVar(key="idex_contract_blockchain",
                  prompt=f"Enter blockchain to interact with IDEX contract ({'/'.join(IDEX_BLOCKCHAINS)})>>> ",
                  required_if=using_exchange(EXCHANGE_NAME),
                  default='ETH',
                  validator=validate_idex_contract_blockchain,
                  is_secure=True,
                  is_connect_key=False),
}
