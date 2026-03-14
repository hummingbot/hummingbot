from typing import Optional

from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def get_grpc_endpoint(domain: str = CONSTANTS.DOMAIN) -> str:
    return CONSTANTS.GRPC_ENDPOINT


def is_paper_trading(domain: str = CONSTANTS.DOMAIN) -> bool:
    return domain == CONSTANTS.PAPER_DOMAIN


def trading_pair_to_architect_symbol(trading_pair: str, venue: str = CONSTANTS.DEFAULT_EXECUTION_VENUE) -> str:
    """
    Convert Hummingbot trading pair to Architect perpetual symbol.
    e.g. 'BTC-USDT' → 'BTC-USDT BINANCE Perpetual'
    """
    return f"{trading_pair} {venue} {CONSTANTS.PERPETUAL_SYMBOL_SUFFIX}"


def architect_symbol_to_trading_pair(symbol: str) -> str:
    """
    Convert Architect perpetual symbol to Hummingbot trading pair.
    e.g. 'BTC-USDT BINANCE Perpetual' → 'BTC-USDT'
    """
    # Strip venue and suffix: "BTC-USDT BINANCE Perpetual" → "BTC-USDT"
    parts = symbol.split(" ")
    if len(parts) >= 1:
        return parts[0]
    return symbol


def is_perpetual_symbol(symbol: str) -> bool:
    """Return True if the symbol represents a perpetual contract."""
    return CONSTANTS.PERPETUAL_SYMBOL_SUFFIX in symbol


def build_api_factory(
    throttler=None,
    auth=None,
    domain: str = CONSTANTS.DOMAIN,
) -> WebAssistantsFactory:
    return WebAssistantsFactory(throttler=throttler, auth=auth)
