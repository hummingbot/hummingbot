import re
from typing import (
    Optional,
    Tuple)

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange


CENTRALIZED = True
EXAMPLE_PAIR = "MDX-USDT"
DEFAULT_FEES = [0.1, 0.1]

TRADING_PAIR_SPLITTER = re.compile(r"^(\w+)(AAVE|ADA|ALPHA|ANKR|ATOM|BAKE|BAND|BCH|BNB|BTCDOWN|BTCUP|BTC|BURGER|BUSD|CAKE|COMP|CREAM|CTK|CTSI|DASH|DOGE|DOT|EGLD|EOS|ETH|GRT|HOT|INJ|JST|KAVA|KNC|KSM|LINK|LRC|LTC|NANO|OGN|ONE|PROM|REEF|SAND|SFP|SLP|SNX|SOL|SPARTA|SRM|SUSHI|SXP|TFUEL|THETA|TRX|TWT|UNFI|UNI|USDT|WAVES|WRX|XLM|XRP|XTZ|XVS|YFII|YFI|ZIL|ZRX|BIDR|USDC|IDRT|MDX)$")


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


def convert_to_mandala_exchange_trading_pair(hb_trading_pair: str) -> str:
    # Mandala uses underscore in split BASEQUOTE (BTC_USDT)
    return hb_trading_pair.replace("-", "_")


def is_mdx_pair(trading_pair: str) -> bool:
    return list(filter(lambda x: x.startswith("MDX"), trading_pair))


KEYS = {
    "mandala_api_key":
        ConfigVar(key="mandala_api_key",
                  prompt="Enter your mandala API key >>> ",
                  required_if=using_exchange("mandala"),
                  is_secure=True,
                  is_connect_key=True),
    "mandala_api_secret":
        ConfigVar(key="mandala_api_secret",
                  prompt="Enter your mandala API secret >>> ",
                  required_if=using_exchange("mandala"),
                  is_secure=True,
                  is_connect_key=True),
}
