from typing import (
    Tuple,
)

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange

CENTRALIZED = True

EXAMPLE_PAIR = "ETH-USDT"

DEFAULT_FEES = [0.1, 0.1]

# Certain asset tokens is different from its name as per displayed on Fmfw Exchange
ASSET_TO_NAME_MAPPING = {  # token: name
    "WAX": "WAXP",
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


def convert_from_exchange_trading_pair(base: str, quote: str) -> str:
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
    "fmfw_api_key":
        ConfigVar(key="fmfw_api_key",
                  prompt="Enter your Fmfw API key >>> ",
                  required_if=using_exchange("fmfw"),
                  is_secure=True,
                  is_connect_key=True),
    "fmfw_secret_key":
        ConfigVar(key="fmfw_secret_key",
                  prompt="Enter your Fmfw secret key >>> ",
                  required_if=using_exchange("fmfw"),
                  is_secure=True,
                  is_connect_key=True),
}
