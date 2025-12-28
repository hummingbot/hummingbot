from typing import Any, Dict
from hummingbot.core.data_type.trade_fee import TradeFeeSchema
from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar

CENTRALIZED = True
EXAMPLE_PAIR = "ETH-USD"
DEFAULT_FEES = [0.02, 0.04] # Maker, Taker
KEYS = {
    "aevo_perpetual_api_key": ConfigVar(
        key="aevo_perpetual_api_key",
        prompt="Enter your Aevo API key: ",
        required_if=using_exchange("aevo_perpetual"),
        is_secure=True,
        is_connect_key=True),
    "aevo_perpetual_api_secret": ConfigVar(
        key="aevo_perpetual_api_secret",
        prompt="Enter your Aevo API secret: ",
        required_if=using_exchange("aevo_perpetual"),
        is_secure=True,
        is_connect_key=True),
}

from hummingbot.core.utils.tracking_nonce import get_tracking_nonce

def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    side = "B" if is_buy else "S"
    return f"{side}-{trading_pair}-{get_tracking_nonce()}"

def convert_to_exchange_symbol(hb_symbol: str) -> str:
    # ETH-USD -> ETH-PERP
    return hb_symbol.replace("-USD", "-PERP")

def convert_to_hb_symbol(exchange_symbol: str) -> str:
    # ETH-PERP -> ETH-USD
    return exchange_symbol.replace("-PERP", "-USD")

def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    pass
    return True
