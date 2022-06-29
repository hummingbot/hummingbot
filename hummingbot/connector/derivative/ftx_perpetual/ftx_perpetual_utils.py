from typing import Optional

from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar

CENTRALIZED = True


EXAMPLE_PAIR = "BTC-USD"


DEFAULT_FEES = [0.02, 0.07]


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> Optional[str]:
    return exchange_trading_pair.replace("PERP", "USD")


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("USD", "PERP")


KEYS = {
    "ftx_perpetual_api_key":
        ConfigVar(key="ftx_perpetual_api_key",
                  prompt="Enter your FTX API key >>> ",
                  required_if=using_exchange("ftx_perpetual"),
                  is_secure=True,
                  is_connect_key=True),
    "ftx_perpetual_secret_key":
        ConfigVar(key="ftx_perpetual_secret_key",
                  prompt="Enter your FTX API secret >>> ",
                  required_if=using_exchange("ftx_perpetual"),
                  is_secure=True,
                  is_connect_key=True),
    "ftx_perpetual_subaccount_name":
        ConfigVar(key="ftx_perpetual_subaccount_name",
                  prompt="Enter your FTX subaccount name (if this is not a subaccount, leave blank) >>> ",
                  required_if=using_exchange("ftx_perpetual"),
                  is_secure=True,
                  is_connect_key=True),
}
