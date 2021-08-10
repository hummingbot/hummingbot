import re
from typing import Optional, Tuple

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange


CENTRALIZED = True


EXAMPLE_PAIR = "BTC-USDT"


DEFAULT_FEES = [0.02, 0.04]

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
    return hb_trading_pair.replace("-", "")


KEYS = {
    "binance_perpetual_api_key":
        ConfigVar(key="binance_perpetual_api_key",
                  prompt="Enter your Binance Perpetual API key >>> ",
                  required_if=using_exchange("binance_perpetual"),
                  is_secure=True,
                  is_connect_key=True),
    "binance_perpetual_api_secret":
        ConfigVar(key="binance_perpetual_api_secret",
                  prompt="Enter your Binance Perpetual API secret >>> ",
                  required_if=using_exchange("binance_perpetual"),
                  is_secure=True,
                  is_connect_key=True),

}

OTHER_DOMAINS = ["binance_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"binance_perpetual_testnet": "binance_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"binance_perpetual_testnet": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"binance_perpetual_testnet": [0.02, 0.04]}
OTHER_DOMAINS_KEYS = {"binance_perpetual_testnet": {
    # add keys for testnet
    "binance_perpetual_testnet_api_key":
        ConfigVar(key="binance_perpetual_testnet_api_key",
                  prompt="Enter your Binance Perpetual testnet API key >>> ",
                  required_if=using_exchange("binance_perpetual_testnet"),
                  is_secure=True,
                  is_connect_key=True),
    "binance_perpetual_testnet_api_secret":
        ConfigVar(key="binance_perpetual_testnet_api_secret",
                  prompt="Enter your Binance Perpetual testnet API secret >>> ",
                  required_if=using_exchange("binance_perpetual_testnet"),
                  is_secure=True,
                  is_connect_key=True),
}}
