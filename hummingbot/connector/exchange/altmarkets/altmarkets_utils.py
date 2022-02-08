import re
from dateutil.parser import parse as dateparse
from typing import (
    Any,
    Dict,
    Optional,
    Tuple,
)

from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange
from .altmarkets_constants import Constants


TRADING_PAIR_SPLITTER = re.compile(Constants.TRADING_PAIR_SPLITTER)

CENTRALIZED = True

EXAMPLE_PAIR = "ALTM-BTC"

DEFAULT_FEES = [0.25, 0.25]


class AltmarketsAPIError(IOError):
    def __init__(self, error_payload: Dict[str, Any]):
        super().__init__(str(error_payload))
        self.error_payload = error_payload


# convert date string to timestamp
def str_date_to_ts(date: str) -> int:
    return int(dateparse(date).timestamp())


# Request ID class
class RequestId:
    """
    Generate request ids
    """
    _request_id: int = 0

    @classmethod
    def generate_request_id(cls) -> int:
        return get_tracking_nonce()


def split_trading_pair(trading_pair: str) -> Optional[Tuple[str, str]]:
    try:
        m = TRADING_PAIR_SPLITTER.match(trading_pair)
        return m.group(1), m.group(2)
    # Exceptions are now logged as warnings in trading pair fetcher
    except Exception:
        return None


def convert_from_exchange_trading_pair(ex_trading_pair: str) -> Optional[str]:
    regex_match = split_trading_pair(ex_trading_pair)
    if regex_match is None:
        return None
    # AltMarkets.io uses lowercase (btcusdt)
    base_asset, quote_asset = split_trading_pair(ex_trading_pair)
    return f"{base_asset.upper()}-{quote_asset.upper()}"


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    # AltMarkets.io uses lowercase (btcusdt)
    return hb_trading_pair.replace("-", "").lower()


def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    side = "B" if is_buy else "S"
    symbols = trading_pair.split("-")
    base = symbols[0].upper()
    quote = symbols[1].upper()
    base_str = f"{base[0:4]}{base[-1]}"
    quote_str = f"{quote[0:2]}{quote[-1]}"
    return f"{Constants.HBOT_BROKER_ID}-{side}{base_str}{quote_str}{get_tracking_nonce()}"


KEYS = {
    "altmarkets_api_key":
        ConfigVar(key="altmarkets_api_key",
                  prompt=f"Enter your {Constants.EXCHANGE_NAME} API key >>> ",
                  required_if=using_exchange("altmarkets"),
                  is_secure=True,
                  is_connect_key=True),
    "altmarkets_secret_key":
        ConfigVar(key="altmarkets_secret_key",
                  prompt=f"Enter your {Constants.EXCHANGE_NAME} secret key >>> ",
                  required_if=using_exchange("altmarkets"),
                  is_secure=True,
                  is_connect_key=True),
}
