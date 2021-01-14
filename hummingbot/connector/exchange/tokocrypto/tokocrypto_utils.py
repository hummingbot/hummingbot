import re
from typing import (
    Optional,
    Tuple)

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange


CENTRALIZED = True
EXAMPLE_PAIR = "USDT-BIDR"
DEFAULT_FEES = [0.1, 0.1]

TRADING_PAIR_SPLITTER = re.compile(r"^(\w+)(BNB|BTC|BUSD|DOT|ETH|ONE|SRM|SXP|USDT|ZIL|BTCDOWN|BTCUP|CAKE|CREAM|DASH|EOS|OGN|TRX|XRP|BAND|BCH|COMP|CTSI|WAVES|YFI|LINK|LINK|KAVA|JST|XTZ|XLM|WRX|UNI|SAND|SOL|SNX|LTC|KNC|EGLD|YFII|BIDR)$")


def split_trading_pair(trading_pair: str) -> Optional[Tuple[str, str]]:
    try:
        m = TRADING_PAIR_SPLITTER.match(trading_pair)
        return m.group(1), m.group(2)
    # Exceptions are now logged as warnings in trading pair fetcher
    except Exception:
        return None


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> Optional[str]:
    if split_trading_pair(exchange_trading_pair) is None:
        return None
    # Binance does not split BASEQUOTE (BTCUSDT)
    base_asset, quote_asset = split_trading_pair(exchange_trading_pair.replace("_", ""))
    return f"{base_asset}-{quote_asset}"


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    # Binance does not split BASEQUOTE (BTCUSDT)
    return hb_trading_pair.replace("-", "")


KEYS = {
    "tokocrypto_api_key":
        ConfigVar(key="tokocrypto_api_key",
                  prompt="Enter your tokocrypto API key >>> ",
                  required_if=using_exchange("tokocrypto"),
                  is_secure=True,
                  is_connect_key=True),
    "tokocrypto_api_secret":
        ConfigVar(key="tokocrypto_api_secret",
                  prompt="Enter your tokocrypto API secret >>> ",
                  required_if=using_exchange("tokocrypto"),
                  is_secure=True,
                  is_connect_key=True),
}

OTHER_DOMAINS = []
OTHER_DOMAINS_PARAMETER = {"tokocrypto_us": "us"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"tokocrypto_us": "USDT-BIDR"}
OTHER_DOMAINS_DEFAULT_FEES = {"tokocrypto_us": [0.1, 0.1]}
OTHER_DOMAINS_KEYS = {"tokocrypto_us": {
    "tokocrypto_us_api_key":
        ConfigVar(key="tokocrypto_us_api_key",
                  prompt="Enter your Tokocrypto US API key >>> ",
                  required_if=using_exchange("tokocrypto_us"),
                  is_secure=True,
                  is_connect_key=True),
    "tokocrypto_us_api_secret":
        ConfigVar(key="tokocrypto_us_api_secret",
                  prompt="Enter your Tokocrypto US API secret >>> ",
                  required_if=using_exchange("tokocrypto_us"),
                  is_secure=True,
                  is_connect_key=True),
}}
