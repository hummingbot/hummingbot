import re
import hummingbot.connector.exchange.binance.binance_constants as CONSTANTS

from typing import Optional, Tuple

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange


CENTRALIZED = True
EXAMPLE_PAIR = "ZRX-ETH"
DEFAULT_FEES = [0.1, 0.1]

SPECIAL_PAIRS = re.compile(r"^(BAT|BNB|HNT|ONT|OXT|USDT|VET)(USD)$")
RE_4_LETTERS_QUOTE = re.compile(r"^(\w{2,})(BIDR|BKRW|BUSD|BVND|IDRT|TUSD|USDC|USDS|USDT)$")
RE_3_LETTERS_QUOTE = re.compile(r"^(\w+)(\w{3})$")


def split_trading_pair(trading_pair: str) -> Optional[Tuple[str, str]]:
    try:
        m = SPECIAL_PAIRS.match(trading_pair)
        if m is None:
            m = RE_4_LETTERS_QUOTE.match(trading_pair)
        if m is None:
            m = RE_3_LETTERS_QUOTE.match(trading_pair)
        return m.group(1), m.group(2)
    # Exceptions are now logged as warnings in trading pair fetcher
    except Exception:
        return None


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> Optional[str]:
    result = None
    splitted_pair = split_trading_pair(exchange_trading_pair)
    if splitted_pair is not None:
        # Binance does not split BASEQUOTE (BTCUSDT)
        base_asset, quote_asset = splitted_pair
        result = f"{base_asset}-{quote_asset}"
    return result


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    # Binance does not split BASEQUOTE (BTCUSDT)
    return hb_trading_pair.replace("-", "")


def public_rest_url(path_url: str, domain: str = "com") -> str:
    return CONSTANTS.REST_URL.format(domain) + CONSTANTS.PUBLIC_API_VERSION + path_url


def private_rest_url(path_url: str, domain: str = "com") -> str:
    return CONSTANTS.REST_URL.format(domain) + CONSTANTS.PRIVATE_API_VERSION + path_url


KEYS = {
    "binance_api_key":
        ConfigVar(key="binance_api_key",
                  prompt="Enter your Binance API key >>> ",
                  required_if=using_exchange("binance"),
                  is_secure=True,
                  is_connect_key=True),
    "binance_api_secret":
        ConfigVar(key="binance_api_secret",
                  prompt="Enter your Binance API secret >>> ",
                  required_if=using_exchange("binance"),
                  is_secure=True,
                  is_connect_key=True),
}

OTHER_DOMAINS = ["binance_us"]
OTHER_DOMAINS_PARAMETER = {"binance_us": "us"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"binance_us": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"binance_us": [0.1, 0.1]}
OTHER_DOMAINS_KEYS = {"binance_us": {
    "binance_us_api_key":
        ConfigVar(key="binance_us_api_key",
                  prompt="Enter your Binance US API key >>> ",
                  required_if=using_exchange("binance_us"),
                  is_secure=True,
                  is_connect_key=True),
    "binance_us_api_secret":
        ConfigVar(key="binance_us_api_secret",
                  prompt="Enter your Binance US API secret >>> ",
                  required_if=using_exchange("binance_us"),
                  is_secure=True,
                  is_connect_key=True),
}}
