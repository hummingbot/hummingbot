from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.settings import required_exchanges

CENTRALIZED = False
EXAMPLE_PAIR = "LUNA-UST"
DEFAULT_FEES = [0., 0.]


KEYS = {
    "sifchain_wallet_address":
        ConfigVar(key="sifchain_wallet_address",
                  prompt="Enter your Keplr wallet address >>> ",
                  required_if=lambda: "sifchain" in required_exchanges,
                  is_secure=True,
                  is_connect_key=True),
    "sifchain_wallet_seeds":
        ConfigVar(key="sifchain_wallet_seeds",
                  prompt="Enter your Keplr wallet seeds >>> ",
                  required_if=lambda: "sifchain" in required_exchanges,
                  is_secure=True,
                  is_connect_key=True),
}
