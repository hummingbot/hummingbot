from typing import Any, Dict, Optional

from hummingbot.connector.derivative.evedex_perpetual import evedex_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def get_trade_base_url(domain: str = CONSTANTS.DOMAIN) -> str:
    if domain == CONSTANTS.TESTNET_DOMAIN:
        return CONSTANTS.TESTNET_TRADE_BASE_URL
    return CONSTANTS.TRADE_BASE_URL


def get_auth_base_url(domain: str = CONSTANTS.DOMAIN) -> str:
    if domain == CONSTANTS.TESTNET_DOMAIN:
        return CONSTANTS.TESTNET_AUTH_BASE_URL
    return CONSTANTS.AUTH_BASE_URL


def get_ws_url(domain: str = CONSTANTS.DOMAIN) -> str:
    if domain == CONSTANTS.TESTNET_DOMAIN:
        return CONSTANTS.TESTNET_WS_URL
    return CONSTANTS.WS_URL


def get_ws_prefix(domain: str = CONSTANTS.DOMAIN) -> str:
    if domain == CONSTANTS.TESTNET_DOMAIN:
        return CONSTANTS.TESTNET_WS_CHANNEL_PREFIX
    return CONSTANTS.WS_CHANNEL_PREFIX


def get_chain_id(domain: str = CONSTANTS.DOMAIN) -> int:
    if domain == CONSTANTS.TESTNET_DOMAIN:
        return CONSTANTS.TESTNET_CHAIN_ID
    return CONSTANTS.CHAIN_ID


def public_rest_url(path: str, domain: str = CONSTANTS.DOMAIN) -> str:
    return get_trade_base_url(domain) + path


def private_rest_url(path: str, domain: str = CONSTANTS.DOMAIN) -> str:
    return get_trade_base_url(domain) + path


def instrument_to_trading_pair(instrument_id: str) -> str:
    """
    Convert EVEDEX instrument ID to Hummingbot trading pair.
    e.g. 'btc-usd' -> 'BTC-USD'
    """
    parts = instrument_id.split("-")
    if len(parts) == 2:
        return f"{parts[0].upper()}-{parts[1].upper()}"
    return instrument_id.upper()


def trading_pair_to_instrument(trading_pair: str) -> str:
    """
    Convert Hummingbot trading pair to EVEDEX instrument ID.
    e.g. 'BTC-USD' -> 'btc-usd'
    """
    return trading_pair.lower()


def ws_channel_name(template: str, domain: str = CONSTANTS.DOMAIN, **kwargs) -> str:
    """Build a fully-qualified Centrifuge channel name with prefix."""
    prefix = get_ws_prefix(domain)
    channel = template.format(**kwargs)
    return f"{prefix}:{channel}"


def is_instrument_active(instrument: Dict[str, Any]) -> bool:
    return (
        instrument.get("visibility") in ("all", None)
        and instrument.get("trading") in ("all", None)
        and instrument.get("marketState") == "OPEN"
    )


def build_api_factory(
    throttler=None,
    auth=None,
    domain: str = CONSTANTS.DOMAIN,
) -> WebAssistantsFactory:
    return WebAssistantsFactory(throttler=throttler, auth=auth)
