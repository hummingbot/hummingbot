from dateutil.parser import parse as dateparse
from typing import (
    Any,
    Dict,
    Optional,
)

from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange
from .coinzoom_constants import Constants


CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USD"

DEFAULT_FEES = [0.2, 0.26]


class CoinzoomAPIError(IOError):
    def __init__(self, error_payload: Dict[str, Any]):
        super().__init__(str(error_payload))
        self.error_payload = error_payload


# convert date string to timestamp
def str_date_to_ts(date: str) -> int:
    return int(dateparse(date).timestamp() * 1e3)


# Request ID class
class RequestId:
    """
    Generate request ids
    """
    _request_id: int = 0

    @classmethod
    def generate_request_id(cls) -> int:
        return get_tracking_nonce()


def convert_from_exchange_trading_pair(ex_trading_pair: str) -> Optional[str]:
    # CoinZoom uses uppercase (BTC/USDT)
    return ex_trading_pair.replace("/", "-")


def convert_to_exchange_trading_pair(hb_trading_pair: str, alternative: bool = False) -> str:
    # CoinZoom uses uppercase (BTCUSDT)
    if alternative:
        return hb_trading_pair.replace("-", "_").upper()
    else:
        return hb_trading_pair.replace("-", "/").upper()


def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    side = "B" if is_buy else "S"
    symbols = trading_pair.split("-")
    base = symbols[0].upper()
    quote = symbols[1].upper()
    base_str = f"{base[0]}{base[-1]}"
    quote_str = f"{quote[0]}{quote[-1]}"
    return f"{Constants.HBOT_BROKER_ID}{side}{base_str}{quote_str}{get_tracking_nonce()}"


KEYS = {
    "coinzoom_api_key":
        ConfigVar(key="coinzoom_api_key",
                  prompt=f"Enter your {Constants.EXCHANGE_NAME} API key >>> ",
                  required_if=using_exchange("coinzoom"),
                  is_secure=True,
                  is_connect_key=True),
    "coinzoom_secret_key":
        ConfigVar(key="coinzoom_secret_key",
                  prompt=f"Enter your {Constants.EXCHANGE_NAME} secret key >>> ",
                  required_if=using_exchange("coinzoom"),
                  is_secure=True,
                  is_connect_key=True),
    "coinzoom_username":
        ConfigVar(key="coinzoom_username",
                  prompt=f"Enter your {Constants.EXCHANGE_NAME} ZoomMe username >>> ",
                  required_if=using_exchange("coinzoom"),
                  is_secure=True,
                  is_connect_key=True),
}
