from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.settings import required_exchanges

CENTRALIZED = False
EXAMPLE_PAIR = "LUNA-UST"
DEFAULT_FEES = [0., 0.]


KEYS = {
    "terra_wallet_address":
        ConfigVar(key="terra_wallet_address",
                  prompt="Enter your Terra wallet address >>> ",
                  required_if=lambda: "terra" in required_exchanges,
                  is_secure=True,
                  is_connect_key=True),
    "terra_wallet_seeds":
        ConfigVar(key="terra_wallet_seeds",
                  prompt="Enter your Terra wallet seeds >>> ",
                  required_if=lambda: "terra" in required_exchanges,
                  is_secure=True,
                  is_connect_key=True),
}
