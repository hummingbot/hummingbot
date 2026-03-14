from typing import Any, Dict, Optional

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.connections.rest_connection import RESTConnection


def get_market_data_url(domain: str = CONSTANTS.DOMAIN) -> str:
    if domain == CONSTANTS.TESTNET_DOMAIN:
        return CONSTANTS.TESTNET_MARKET_DATA_BASE_URL
    return CONSTANTS.MARKET_DATA_BASE_URL


def get_trade_data_url(domain: str = CONSTANTS.DOMAIN) -> str:
    if domain == CONSTANTS.TESTNET_DOMAIN:
        return CONSTANTS.TESTNET_TRADE_DATA_BASE_URL
    return CONSTANTS.TRADE_DATA_BASE_URL


def get_edge_url(domain: str = CONSTANTS.DOMAIN) -> str:
    if domain == CONSTANTS.TESTNET_DOMAIN:
        return CONSTANTS.TESTNET_EDGE_BASE_URL
    return CONSTANTS.EDGE_BASE_URL


def get_market_ws_url(domain: str = CONSTANTS.DOMAIN) -> str:
    if domain == CONSTANTS.TESTNET_DOMAIN:
        return CONSTANTS.TESTNET_MARKET_DATA_WS_URL
    return CONSTANTS.MARKET_DATA_WS_URL


def get_trade_ws_url(domain: str = CONSTANTS.DOMAIN) -> str:
    if domain == CONSTANTS.TESTNET_DOMAIN:
        return CONSTANTS.TESTNET_TRADE_DATA_WS_URL
    return CONSTANTS.TRADE_DATA_WS_URL


def public_rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
    """Return full URL for public (market data) endpoints."""
    return get_market_data_url(domain) + path_url


def private_rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
    """Return full URL for private (trade) endpoints."""
    return get_trade_data_url(domain) + path_url


def build_api_factory(
    throttler=None,
    auth=None,
    domain: str = CONSTANTS.DOMAIN,
) -> WebAssistantsFactory:
    from hummingbot.core.web_assistant.auth import AuthBase
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
    )
    return api_factory


def is_exchange_information_valid(instrument: Dict[str, Any]) -> bool:
    """Check if an instrument is tradeable."""
    return (
        instrument.get("is_active", True)
        and instrument.get("kind") == "PERPETUAL"
    )


def instrument_to_trading_pair(instrument: str) -> str:
    """
    Convert GRVT instrument name to Hummingbot trading pair.
    e.g. 'BTC_USDT_Perp' -> 'BTC-USDT'
    """
    parts = instrument.split("_")
    if len(parts) >= 2:
        return f"{parts[0]}-{parts[1]}"
    return instrument


def trading_pair_to_instrument(trading_pair: str) -> str:
    """
    Convert Hummingbot trading pair to GRVT instrument name.
    e.g. 'BTC-USDT' -> 'BTC_USDT_Perp'
    """
    parts = trading_pair.split("-")
    if len(parts) == 2:
        return f"{parts[0]}_{parts[1]}_Perp"
    return trading_pair


def get_current_server_time_ms() -> int:
    import time
    return int(time.time() * 1000)


def get_expiration_ns(seconds_from_now: int = 3600) -> int:
    """Return expiration timestamp in nanoseconds."""
    import time
    return int((time.time() + seconds_from_now) * 1e9)
