from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import new_fee_config_var, using_exchange

CENTRALIZED = True

EXAMPLE_PAIR = "ETH-USDT"

DEFAULT_FEES = [0.1, 0.1]

FEE_OVERRIDE_MAP = {
    "kucoin_maker_fee": new_fee_config_var("kucoin_maker_fee"),
    "kucoin_taker_fee": new_fee_config_var("kucoin_taker_fee")
}

KEYS = {
    "kucoin_api_key":
        ConfigVar(key="kucoin_api_key",
                  prompt="Enter your KuCoin API key >>> ",
                  required_if=using_exchange("kucoin"),
                  is_secure=True,
                  is_connect_key=True),
    "kucoin_secret_key":
        ConfigVar(key="kucoin_secret_key",
                  prompt="Enter your KuCoin secret key >>> ",
                  required_if=using_exchange("kucoin"),
                  is_secure=True,
                  is_connect_key=True),
    "kucoin_passphrase":
        ConfigVar(key="kucoin_passphrase",
                  prompt="Enter your KuCoin passphrase >>> ",
                  required_if=using_exchange("kucoin"),
                  is_secure=True,
                  is_connect_key=True),
}
