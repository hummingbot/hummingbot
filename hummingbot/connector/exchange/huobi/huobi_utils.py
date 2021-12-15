import re
from typing import (
    Optional,
    Tuple)
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange
from hummingbot.connector.exchange.huobi.huobi_ws_post_processor import HuobiWSPostProcessor
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce

from hummingbot.core.event.events import (
    TradeType
)
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


RE_4_LETTERS_QUOTE = re.compile(r"^(\w+)(usdt|husd|usdc)$")
RE_3_LETTERS_QUOTE = re.compile(r"^(\w+)(btc|eth|trx)$")
RE_2_LETTERS_QUOTE = re.compile(r"^(\w+)(ht)$")

CENTRALIZED = True

EXAMPLE_PAIR = "ETH-USDT"

DEFAULT_FEES = [0.2, 0.2]

BROKER_ID = "AAc484720a"


def split_trading_pair(trading_pair: str) -> Optional[Tuple[str, str]]:
    try:
        m = RE_4_LETTERS_QUOTE.match(trading_pair)
        if m is None:
            m = RE_3_LETTERS_QUOTE.match(trading_pair)
            if m is None:
                m = RE_2_LETTERS_QUOTE.match(trading_pair)
        return m.group(1), m.group(2)
    # Exceptions are now logged as warnings in trading pair fetcher
    except Exception:
        return None


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> Optional[str]:
    if split_trading_pair(exchange_trading_pair) is None:
        return None
    # Huobi uses lowercase (btcusdt)
    base_asset, quote_asset = split_trading_pair(exchange_trading_pair)
    return f"{base_asset.upper()}-{quote_asset.upper()}"


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    # Huobi uses lowercase (btcusdt)
    return hb_trading_pair.replace("-", "").lower()


def get_new_client_order_id(trade_type: TradeType, trading_pair: str) -> str:
    side = ""
    if trade_type is TradeType.BUY:
        side = "buy"
    if trade_type is TradeType.SELL:
        side = "sell"
    tracking_nonce = get_tracking_nonce()
    return f"{BROKER_ID}-{side}-{trading_pair}-{tracking_nonce}"


def build_api_factory() -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(ws_post_processors=[HuobiWSPostProcessor()])
    return api_factory


KEYS = {
    "huobi_api_key":
        ConfigVar(key="huobi_api_key",
                  prompt="Enter your Huobi API key >>> ",
                  required_if=using_exchange("huobi"),
                  is_secure=True,
                  is_connect_key=True),
    "huobi_secret_key":
        ConfigVar(key="huobi_secret_key",
                  prompt="Enter your Huobi secret key >>> ",
                  required_if=using_exchange("huobi"),
                  is_secure=True,
                  is_connect_key=True),
}
