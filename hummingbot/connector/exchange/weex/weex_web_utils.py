from __future__ import annotations

from typing import Optional, Any

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

from hummingbot.connector.exchange.weex import weex_constants as CONSTANTS
from hummingbot.connector.exchange.weex.weex_auth import WeexAuth


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return f"{CONSTANTS.REST_URLS[domain]}{path_url}"


def private_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return f"{CONSTANTS.REST_URLS[domain]}{path_url}"


def ws_public_url(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return CONSTANTS.WS_PUBLIC_URLS[domain]


def ws_private_url(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return CONSTANTS.WS_PRIVATE_URLS[domain]


def is_success_response(resp: dict) -> bool:
    return str(resp.get("code")) == CONSTANTS.SUCCESS_CODE


def build_api_factory(throttler: AsyncThrottler, auth: Optional[WeexAuth] = None, **kwargs) -> WebAssistantsFactory:
    return WebAssistantsFactory(throttler=throttler, auth=auth)


