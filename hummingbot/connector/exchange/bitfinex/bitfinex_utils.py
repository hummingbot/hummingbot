import math

from typing import Dict, List, Tuple, Optional
from decimal import Decimal


from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange


CENTRALIZED = True


EXAMPLE_PAIR = "ETH-USD"

# BitFinex list Tether(USDT) as 'UST'
EXCHANGE_TO_HB_CONVERSION = {"UST": "USDT"}
HB_TO_EXCHANGE_CONVERSION = {v: k for k, v in EXCHANGE_TO_HB_CONVERSION.items()}

DEFAULT_FEES = [0.1, 0.2]


KEYS = {
    "bitfinex_api_key":
        ConfigVar(key="bitfinex_api_key",
                  prompt="Enter your Bitfinex API key >>> ",
                  required_if=using_exchange("bitfinex"),
                  is_secure=True,
                  is_connect_key=True),
    "bitfinex_secret_key":
        ConfigVar(key="bitfinex_secret_key",
                  prompt="Enter your Bitfinex secret key >>> ",
                  required_if=using_exchange("bitfinex"),
                  is_secure=True,
                  is_connect_key=True),
}


# deeply merge two dictionaries
def merge_dicts(source: Dict, destination: Dict) -> Dict:
    for key, value in source.items():
        if isinstance(value, dict):
            # get node or create one
            node = destination.setdefault(key, {})
            merge_dicts(value, node)
        else:
            destination[key] = value

    return destination


# join paths
def join_paths(*paths: List[str]) -> str:
    return "/".join(paths)


# get precision decimal from a number
def get_precision(precision: int) -> Decimal:
    return Decimal(1) / Decimal(math.pow(10, precision))


def split_trading_pair(trading_pair: str) -> Tuple[str, str]:
    try:
        base, quote = trading_pair.split("-")
        return base, quote
    # exceptions are now logged as warnings in trading pair fetcher
    except Exception as e:
        raise e


def split_trading_pair_from_exchange(trading_pair: str) -> Tuple[str, str]:
    # sometimes the exchange returns trading pairs like tBTCUSD
    isTradingPair = trading_pair[0].islower() and trading_pair[1].isupper() and trading_pair[0] == "t"
    pair = trading_pair[1:] if isTradingPair else trading_pair

    if ":" in pair:
        base, quote = pair.split(":")
    elif len(pair) == 6:
        base, quote = pair[:3], pair[3:]
    else:
        return None
    return base, quote


def valid_exchange_trading_pair(trading_pair: str) -> bool:
    try:
        base, quote = split_trading_pair_from_exchange(trading_pair)
        return True
    except Exception:
        return False


def convert_from_exchange_token(token: str) -> str:
    if token in EXCHANGE_TO_HB_CONVERSION:
        token = EXCHANGE_TO_HB_CONVERSION[token]
    return token


def convert_to_exchange_token(token: str) -> str:
    if token in HB_TO_EXCHANGE_CONVERSION:
        token = HB_TO_EXCHANGE_CONVERSION[token]
    return token


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> Optional[str]:
    try:
        base_asset, quote_asset = split_trading_pair_from_exchange(exchange_trading_pair)

        base_asset = convert_from_exchange_token(base_asset)
        quote_asset = convert_from_exchange_token(quote_asset)

        return f"{base_asset}-{quote_asset}"
    except Exception as e:
        raise e


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    base_asset, quote_asset = hb_trading_pair.split("-")

    base_asset = convert_to_exchange_token(base_asset)
    quote_asset = convert_to_exchange_token(quote_asset)

    if len(base_asset) > 3:  # Adds ':' delimiter if base asset > 3 characters
        trading_pair = f"t{base_asset}:{quote_asset}"
    else:
        trading_pair = f"t{base_asset}{quote_asset}"
    return trading_pair
