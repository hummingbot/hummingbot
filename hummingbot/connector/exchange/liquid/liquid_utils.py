from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import new_fee_config_var, using_exchange

CENTRALIZED = True

EXAMPLE_PAIR = "ETH-USD"

DEFAULT_FEES = [0.1, 0.1]

FEE_OVERRIDE_MAP = {
    "liquid_maker_fee": new_fee_config_var("liquid_maker_fee"),
    "liquid_taker_fee": new_fee_config_var("liquid_taker_fee")
}

KEYS = {
    "liquid_api_key":
        ConfigVar(key="liquid_api_key",
                  prompt="Enter your Liquid API key >>> ",
                  required_if=using_exchange("liquid"),
                  is_secure=True,
                  is_connect_key=True),
    "liquid_secret_key":
        ConfigVar(key="liquid_secret_key",
                  prompt="Enter your Liquid secret key >>> ",
                  required_if=using_exchange("liquid"),
                  is_secure=True,
                  is_connect_key=True),
}
