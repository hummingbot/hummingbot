from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import new_fee_config_var, using_exchange

CENTRALIZED = True

EXAMPLE_PAIR = "ETH-USDC"

DEFAULT_FEES = [0.5, 0.5]

FEE_OVERRIDE_MAP = {
    "coinbase_pro_maker_fee": new_fee_config_var("coinbase_pro_maker_fee"),
    "coinbase_pro_taker_fee": new_fee_config_var("coinbase_pro_taker_fee")
}

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
