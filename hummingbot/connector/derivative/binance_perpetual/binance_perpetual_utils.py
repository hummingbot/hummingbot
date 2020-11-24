import re
from typing import Optional, Tuple

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange


CENTRALIZED = True


EXAMPLE_PAIR = "BTC-USDT"


DEFAULT_FEES = [0.02, 0.04]


RE_4_LETTERS_QUOTE = re.compile(r"^(\w+)(USDT|USDC|USDS|TUSD|BUSD|IDRT|BKRW|BIDR)$")
RE_3_LETTERS_QUOTE = re.compile(r"^(\w+)(BTC|ETH|BNB|DAI|XRP|PAX|TRX|NGN|RUB|TRY|EUR|ZAR|UAH|GBP|USD|BRL)$")


# Helper Functions ---
def split_trading_pair(trading_pair: str) -> Optional[Tuple[str, str]]:
    try:
        m = RE_4_LETTERS_QUOTE.match(trading_pair)
        if m is None:
            m = RE_3_LETTERS_QUOTE.match(trading_pair)
        return m.group(1), m.group(2)
    except Exception as e:
        raise e


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> Optional[str]:
    if split_trading_pair(exchange_trading_pair) is None:
        return None
    base_asset, quote_asset = split_trading_pair(exchange_trading_pair)
    return f"{base_asset}-{quote_asset}"


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
