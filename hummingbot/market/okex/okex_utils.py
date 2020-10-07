from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange


CENTRALIZED = True


EXAMPLE_PAIR = "BTC-USDT"


DEFAULT_FEES = [0.1, 0.15]


KEYS = {
    "okex_api_key":
        ConfigVar(key="okex_api_key",
                  prompt="Enter your OKEx API key >>> ",
                  required_if=using_exchange("okex"),
                  is_secure=True),
    "okex_secret_key":
        ConfigVar(key="new_market_secret_key",
                  prompt="Enter your OKEx secret key >>> ",
                  required_if=using_exchange("okex"),
                  is_secure=True),
    "okex_passphrase":
        ConfigVar(key="okex_passphrase",
                  prompt="Enter your OKEx passphrase key >>> ",
                  required_if=using_exchange("okex"),
                  is_secure=True),
}
