from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange


CENTRALIZED = True


EXAMPLE_PAIR = "BTC-USD"


DEFAULT_FEES = [0.05, 0.2]


KEYS = {
    "dydx_perpetual_api_key":
        ConfigVar(key="dydx_perpetual_api_key",
                  prompt="Enter your dydx Perpetual API key >>> ",
                  required_if=using_exchange("dydx_perpetual"),
                  is_secure=True,
                  is_connect_key=True),
    "dydx_perpetual_api_secret":
        ConfigVar(key="dydx_perpetual_api_secret",
                  prompt="Enter your dydx Perpetual API secret >>> ",
                  required_if=using_exchange("dydx_perpetual"),
                  is_secure=True,
                  is_connect_key=True),
    "dydx_perpetual_passphrase":
        ConfigVar(key="dydx_perpetual_passphrase",
                  prompt="Enter your dydx Perpetual API passphrase >>> ",
                  required_if=using_exchange("dydx_perpetual"),
                  is_secure=True,
                  is_connect_key=True),
    "dydx_perpetual_account_number":
        ConfigVar(key="dydx_perpetual_account_number",
                  prompt="Enter your dydx Perpetual API account_number >>> ",
                  required_if=using_exchange("dydx_perpetual"),
                  is_secure=True,
                  is_connect_key=True),
    "dydx_perpetual_stark_private_key":
        ConfigVar(key="dydx_perpetual_stark_private_key",
                  prompt="Enter your stark private key >>> ",
                  required_if=using_exchange("dydx_perpetual"),
                  is_secure=True,
                  is_connect_key=True),
    "dydx_perpetual_ethereum_address":
        ConfigVar(key="dydx_perpetual_ethereum_address",
                  prompt="Enter your ethereum wallet address >>> ",
                  required_if=using_exchange("dydx_perpetual"),
                  is_secure=True,
                  is_connect_key=True),
}
