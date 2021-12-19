from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.settings import required_exchanges

CENTRALIZED = False


KEYS = {
    "solana_wallet_address":
        ConfigVar(key="solana_wallet_address",
                  prompt="Enter your Solana wallet address >>> ",
                  required_if=lambda: "solana" in required_exchanges,
                  is_secure=True,
                  is_connect_key=True),
    "solana_wallet_private_key":
        ConfigVar(key="solana_wallet_private_key",
                  prompt="Enter your Solana wallet private key (as Base68) >>> ",
                  required_if=lambda: "solana" in required_exchanges,
                  is_secure=True,
                  is_connect_key=True),
}
