from hummingbot.connector.derivative.reya_perpetual import reya_perpetual_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return CONSTANTS.REST_URLS[domain] + CONSTANTS.V2_PATH + path_url.lstrip("/")


def private_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return public_rest_url(path_url, domain)


def api_wallet_status_url(address: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return CONSTANTS.REST_URLS[domain] + CONSTANTS.API_WALLET_STATUS_PATH.format(address=address.lower())


def wss_url(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return CONSTANTS.WS_URLS[domain]


def build_api_factory(throttler: AsyncThrottler = None, auth: AuthBase = None) -> WebAssistantsFactory:
    return WebAssistantsFactory(throttler=throttler or AsyncThrottler(CONSTANTS.RATE_LIMITS), auth=auth)


def is_exchange_information_valid(market: dict) -> bool:
    return market.get("status") == "TRADING" and market.get("symbol", "").endswith(CONSTANTS.SYMBOL_SUFFIX)
