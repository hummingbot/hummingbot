import re
from typing import Optional, Tuple

from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar

CENTRALIZED = True

EXAMPLE_PAIR = "ETH-USDT"

DEFAULT_FEES = [0.2, 0.2]

KEYS = {
    "coinex_api_key":
        ConfigVar(key="coinex_api_key",
                  prompt="Enter your CoinEx API key >>> ",
                  required_if=using_exchange("coinex"),
                  is_secure=True,
                  is_connect_key=True),
    "coinex_secret_key":
        ConfigVar(key="coinex_secret_key",
                  prompt="Enter your CoinEx secret key >>> ",
                  required_if=using_exchange("coinex"),
                  is_secure=True,
                  is_connect_key=True),
}

RE_4_LETTERS_QUOTE = re.compile(r"^(\w+)(USDT|USDC|USDS|TUSD|BUSD|IDRT|BKRW|BIDR|BVND)$")
RE_3_LETTERS_QUOTE = re.compile(r"^(\w+)(BTC|ETH|BNB|DAI|XRP|PAX|TRX|NGN|RUB|TRY|EUR|ZAR|UAH|GBP|USD|BRL|AUD|VAI|BCH)$")

USD_QUOTES = ["DAI", "USDT", "USDC", "USDS", "TUSD", "PAX", "BUSD", "USD"]


def split_trading_pair(trading_pair: str) -> Optional[Tuple[str, str]]:
    try:
        m = RE_4_LETTERS_QUOTE.match(trading_pair)
        if m is None:
            m = RE_3_LETTERS_QUOTE.match(trading_pair)
        return m.group(1), m.group(2)
    # Exceptions are now logged as warnings in trading pair fetcher
    except Exception:
        return None


def convert_from_exchange_trading_pair(exchange_trading_pair: str, quote: Optional[str] = None) -> Optional[str]:
    if quote is None:
        if split_trading_pair(exchange_trading_pair) is None:
            return None
        base_asset, quote_asset = split_trading_pair(exchange_trading_pair)
    else:
        try:
            m = re.compile(rf"^(\w+)({quote})$").match(exchange_trading_pair)
            base_asset, quote_asset = m.group(1), m.group(2)
        except Exception:
            return None
    # CoinEx does not split BASEQUOTE (BTCUSDT)
    return f"{base_asset}-{quote_asset}"


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    # CoinEx does not split BASEQUOTE (BTCUSDT)
    return hb_trading_pair.replace("-", "")
