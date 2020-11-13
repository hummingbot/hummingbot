from typing import List

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange

CENTRALIZED = False
EXAMPLE_PAIR = "LUNA-UST"
DEFAULT_FEES = [0., 0.]


async def fetch_trading_pairs() -> List[str]:
    # Todo: find all available trading pairs
    return ["LUNA-UST", "LUNA-KRT", "LUNA-SDT", "UST-KRT", "UST-SDT", "KRT-SDT"]

KEYS = {
    "terra_private_key":
        ConfigVar(key="terra_private_key",
                  prompt="Enter your Terra wallet private key >>> ",
                  required_if=using_exchange("terra"),
                  is_secure=True,
                  is_connect_key=True),
}
