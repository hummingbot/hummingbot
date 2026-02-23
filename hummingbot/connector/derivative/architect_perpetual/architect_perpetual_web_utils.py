from __future__ import annotations

from typing import Optional

from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.web_assistants_factory import ConnectionsFactory, WebAssistantsFactory
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant


def _domain_to_rest_base_url(domain: str) -> str:
    # Allow passing a full URL as "domain" for tests/custom deployments
    if domain.startswith("http://") or domain.startswith("https://"):
        return domain.rstrip("/")
    if domain == CONSTANTS.DOMAIN:
        return CONSTANTS.DEFAULT_REST_BASE_URL
    # Fallback: interpret as subdomain prefix
    return f"https://api.{domain}.x.architect.co"


def _domain_to_ws_base_url(domain: str) -> str:
    if domain.startswith("ws://") or domain.startswith("wss://"):
        return domain.rstrip("/")
    if domain == CONSTANTS.DOMAIN:
        return CONSTANTS.DEFAULT_WSS_BASE_URL
    return f"wss://ws.{domain}.x.architect.co"


def public_rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
    return f"{_domain_to_rest_base_url(domain)}{path_url}"


def private_rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
    return public_rest_url(path_url, domain)


def public_ws_url(domain: str = CONSTANTS.DOMAIN) -> str:
    return f"{_domain_to_ws_base_url(domain)}{CONSTANTS.PUBLIC_WS_PATH}"


def private_ws_url(domain: str = CONSTANTS.DOMAIN) -> str:
    return f"{_domain_to_ws_base_url(domain)}{CONSTANTS.PRIVATE_WS_PATH}"


def build_api_factory(throttler, time_synchronizer, domain: str = CONSTANTS.DOMAIN, auth=None) -> WebAssistantsFactory:
    return WebAssistantsFactory(
        throttler=throttler,
        time_synchronizer=time_synchronizer,
        auth=auth,
        rest_pre_processors=None,
        ws_pre_processors=None,
        connections_factory=ConnectionsFactory(),
    )


async def api_request(
    api_factory: WebAssistantsFactory,
    throttler,
    domain: str,
    path_url: str,
    method: RESTMethod = RESTMethod.GET,
    is_auth_required: bool = False,
    params: Optional[dict] = None,
    data: Optional[dict] = None,
    headers: Optional[dict] = None,
):
    rest: RESTAssistant = await api_factory.get_rest_assistant()
    url = private_rest_url(path_url, domain) if is_auth_required else public_rest_url(path_url, domain)
    return await rest.execute_request(
        url=url,
        method=method,
        params=params,
        data=data,
        headers=headers,
        is_auth_required=is_auth_required,
        throttler_limit_id="REST",
    )
