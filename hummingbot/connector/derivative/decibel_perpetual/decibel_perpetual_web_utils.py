from typing import Optional

import hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def get_rest_url(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """Return the REST base URL for the given domain."""
    if domain == CONSTANTS.TESTNET_DOMAIN:
        return CONSTANTS.TESTNET_BASE_URL
    return CONSTANTS.MAINNET_BASE_URL


def fullnode_url(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """Return the Aptos fullnode URL for the given domain."""
    if domain == CONSTANTS.TESTNET_DOMAIN:
        return CONSTANTS.TESTNET_FULLNODE_URL
    return CONSTANTS.MAINNET_FULLNODE_URL


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """Return the full REST URL for public (unauthenticated) endpoints."""
    return get_rest_url(domain) + path_url


def private_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """Return the full REST URL for private (authenticated) endpoints."""
    return get_rest_url(domain) + path_url


def build_api_factory(
    throttler=None,
    auth=None,
    domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> WebAssistantsFactory:
    """Create and return a WebAssistantsFactory for REST communication."""
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
    )
    return api_factory


def is_exchange_information_valid(market: dict) -> bool:
    """
    Return True if a market entry from the Decibel API is valid and active.

    :param market: Market dict as returned by /api/v1/markets
    """
    return bool(market.get("market_name")) and market.get("active", True)
