import time
from typing import Optional

from hummingbot.connector.exchange.twofinance import twofinance_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

_REST_URLS = {
    CONSTANTS.DEFAULT_DOMAIN: CONSTANTS.REST_URL,
    CONSTANTS.TESTNET_DOMAIN: CONSTANTS.TESTNET_REST_URL,
}
_WSS_URLS = {
    CONSTANTS.DEFAULT_DOMAIN: CONSTANTS.WSS_URL,
    CONSTANTS.TESTNET_DOMAIN: CONSTANTS.TESTNET_WSS_URL,
}


def private_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return rest_url(path_url=path_url, domain=domain)


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return rest_url(path_url=path_url, domain=domain)


def rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return _REST_URLS.get(domain, CONSTANTS.REST_URL).rstrip("/") + path_url


def wss_url(domain: str = CONSTANTS.DEFAULT_DOMAIN, override_url: Optional[str] = None) -> str:
    return override_url or _WSS_URLS.get(domain, CONSTANTS.WSS_URL)


def normalize_trading_pair(value: str | None) -> str:
    return str(value or "").replace("/", "-")


def exchange_trading_pair(value: str | None) -> str:
    return str(value or "").replace("-", "/")


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    return WebAssistantsFactory(throttler=throttler, auth=auth)


async def get_current_server_time(throttler, domain) -> float:
    return time.time()
