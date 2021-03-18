import re
from typing import Optional, Tuple

CENTRALIZED = False
EXAMPLE_PAIR = "ETH-USDC"
DEFAULT_FEES = [0.1, 0.1]

USE_ETHEREUM_WALLET = True
# FEE_TYPE = "FlatFee"
# FEE_TOKEN = "XDAI"

USE_ETH_GAS_LOOKUP = False

QUOTE = re.compile(r"^(\w+)(USDC|USDT)$")


# Helper Functions ---
def split_trading_pair(trading_pair: str) -> Optional[Tuple[str, str]]:
    try:
        m = QUOTE.match(trading_pair)
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
