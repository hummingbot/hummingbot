from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange
from hummingbot.connector.exchange.idex.utils import EXCHANGE_NAME

CENTRALIZED = False

USE_ETHEREUM_WALLET = False

EXAMPLE_PAIR = "IDEX-ETH"

DEFAULT_FEES = [0.1, 0.2]

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
}
