import time
from typing import Any, Dict, Optional

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class GrvtPerpetualRESTPreProcessor(RESTPreProcessorBase):

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        request.headers["Content-Type"] = "application/json"
        return request


def public_rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
    """Build URL for public (market data) endpoints."""
    if domain == CONSTANTS.DOMAIN:
        base_url = CONSTANTS.MARKET_DATA_BASE_URL
    else:
        base_url = CONSTANTS.TESTNET_MARKET_DATA_BASE_URL
    return base_url + path_url


def private_rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
    """Build URL for private (trading) endpoints."""
    if domain == CONSTANTS.DOMAIN:
        base_url = CONSTANTS.PERPETUAL_BASE_URL
    else:
        base_url = CONSTANTS.TESTNET_BASE_URL
    return base_url + path_url


def auth_url(domain: str = CONSTANTS.DOMAIN) -> str:
    """Build URL for authentication endpoint."""
    if domain == CONSTANTS.DOMAIN:
        return CONSTANTS.AUTH_BASE_URL
    else:
        return CONSTANTS.TESTNET_AUTH_BASE_URL


def wss_url(domain: str = CONSTANTS.DOMAIN) -> str:
    """Build WebSocket URL for public market data streams."""
    if domain == CONSTANTS.DOMAIN:
        return CONSTANTS.PERPETUAL_WS_URL
    else:
        return CONSTANTS.TESTNET_WS_URL


def trade_wss_url(domain: str = CONSTANTS.DOMAIN) -> str:
    """Build WebSocket URL for private trading streams."""
    if domain == CONSTANTS.DOMAIN:
        return CONSTANTS.PERPETUAL_TRADE_WS_URL
    else:
        return CONSTANTS.TESTNET_TRADE_WS_URL


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = CONSTANTS.DOMAIN,
        auth: Optional[AuthBase] = None) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[
            GrvtPerpetualRESTPreProcessor(),
        ])
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[GrvtPerpetualRESTPreProcessor()])
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = CONSTANTS.DOMAIN,
) -> float:
    """
    GRVT does not expose a dedicated public server-time endpoint.
    Return local wall time in milliseconds for offset sync compatibility.
    """
    return time.time() * 1e3


def is_exchange_information_valid(rule: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information.

    GRVT perpetual instruments follow the pattern: BASE_QUOTE_Perp (e.g. BTC_USDT_Perp).
    """
    instrument = str(rule.get("instrument", ""))
    kind = str(rule.get("kind", "")).upper()
    is_perpetual = kind == "PERPETUAL" or instrument.endswith("_Perp")
    if not is_perpetual:
        return False

    if "is_active" in rule:
        return bool(rule.get("is_active"))

    status = str(rule.get("status", rule.get("state", ""))).lower()
    if status:
        return status in {"active", "enabled", "open", "trading", "online"}

    # If no explicit status is provided, assume active for perpetual instruments.
    return True


def convert_to_exchange_trading_pair(trading_pair: str) -> str:
    """
    Converts a hummingbot trading pair (BASE-QUOTE) to GRVT instrument format (BASE_QUOTE_Perp).
    """
    base, quote = trading_pair.split("-")
    return f"{base}_{quote}_Perp"


def convert_from_exchange_trading_pair(exchange_symbol: str) -> str:
    """
    Converts a GRVT instrument (BASE_QUOTE_Perp) to hummingbot trading pair (BASE-QUOTE).
    """
    parts = exchange_symbol.split("_")
    if len(parts) >= 3 and parts[-1] == "Perp":
        base = parts[0]
        quote = parts[1]
        return f"{base}-{quote}"
    return exchange_symbol
