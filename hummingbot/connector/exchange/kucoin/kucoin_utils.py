from typing import (
    Tuple,
)

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange

CENTRALIZED = True

EXAMPLE_PAIR = "ETH-USDT"

DEFAULT_FEES = [0.1, 0.1]

# Certain asset tokens is different from its name as per displayed on Kucoin Exchange
ASSET_TO_NAME_MAPPING = {  # token: name
    "WAX": "WAXP",
    "BCHSV": "BSV",
}

NAME_TO_ASSET_MAPPING = {  # name: token
    name: asset
    for asset, name in ASSET_TO_NAME_MAPPING.items()
}


def split_trading_pair(trading_pair: str) -> Tuple[str, str]:
    try:
        base, quote = trading_pair.split("-")

        if base in ASSET_TO_NAME_MAPPING:
            base = ASSET_TO_NAME_MAPPING[base]

        if quote in ASSET_TO_NAME_MAPPING:
            quote = ASSET_TO_NAME_MAPPING[quote]

        return base, quote
    except Exception as e:
        raise ValueError(f"Error parsing trading_pair {trading_pair}: {str(e)}")


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    base, quote = exchange_trading_pair.split("-")
    if base in ASSET_TO_NAME_MAPPING:
        base = ASSET_TO_NAME_MAPPING[base]

    if quote in ASSET_TO_NAME_MAPPING:
        quote = ASSET_TO_NAME_MAPPING[quote]

    return f"{base}-{quote}"


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    base, quote = hb_trading_pair.split("-")

    if base in NAME_TO_ASSET_MAPPING:
        base = NAME_TO_ASSET_MAPPING[base]

    if quote in NAME_TO_ASSET_MAPPING:
        quote = NAME_TO_ASSET_MAPPING[quote]

    return f"{base}-{quote}"


def convert_asset_from_exchange(asset: str) -> str:
    if asset in ASSET_TO_NAME_MAPPING:
        asset = ASSET_TO_NAME_MAPPING[asset]
    return asset


def convert_asset_to_exchange(asset: str) -> str:
    if asset in NAME_TO_ASSET_MAPPING:
        asset = NAME_TO_ASSET_MAPPING[asset]
    return asset


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
