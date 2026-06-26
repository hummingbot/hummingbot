import time
from typing import Any, Callable, Optional

from hummingbot.connector.derivative.decibel_perpetual import decibel_perpetual_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full REST URL for public endpoints.

    :param path_url: The API endpoint path
    :param domain: The domain (mainnet, netna, or testnet)
    :return: The full URL
    """
    if domain == CONSTANTS.NETNA_DOMAIN:
        base_url = CONSTANTS.NETNA_REST_URL
    elif domain == CONSTANTS.TESTNET_DOMAIN:
        base_url = CONSTANTS.TESTNET_REST_URL
    else:
        base_url = CONSTANTS.REST_URL
    return base_url + path_url


def private_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full REST URL for private endpoints.

    :param path_url: The API endpoint path
    :param domain: The domain (mainnet or testnet)
    :return: The full URL
    """
    # For Decibel, private and public endpoints use the same base URL
    return public_rest_url(path_url, domain)


def wss_url(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates the WebSocket URL.

    :param domain: The domain (mainnet, netna, or testnet)
    :return: The WebSocket URL
    """
    if domain == CONSTANTS.NETNA_DOMAIN:
        return CONSTANTS.NETNA_WSS_URL
    elif domain == CONSTANTS.TESTNET_DOMAIN:
        return CONSTANTS.TESTNET_WSS_URL
    else:
        return CONSTANTS.WSS_URL


def fullnode_url(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates the Aptos fullnode URL for transaction submission.

    :param domain: The domain (mainnet, netna, or testnet)
    :return: The fullnode URL
    """
    if domain == CONSTANTS.NETNA_DOMAIN:
        return CONSTANTS.NETNA_FULLNODE_URL
    elif domain == CONSTANTS.TESTNET_DOMAIN:
        return CONSTANTS.TESTNET_FULLNODE_URL
    else:
        return CONSTANTS.FULLNODE_URL


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    time_synchronizer: Optional[TimeSynchronizer] = None,
    domain: str = CONSTANTS.DEFAULT_DOMAIN,
    time_provider: Optional[Callable] = None,
    auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    """
    Builds a WebAssistantsFactory for Decibel API requests.

    :param throttler: The rate limiter
    :param time_synchronizer: Time synchronizer for handling server time differences
    :param domain: The domain (mainnet or testnet)
    :param time_provider: Callable that returns current server time
    :param auth: The authenticator (not used for REST API, only for transactions)
    :return: The WebAssistantsFactory instance
    """
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
    )
    return api_factory


def get_package_address(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Gets the Aptos package address for the given domain.

    :param domain: The domain (mainnet, netna, or testnet)
    :return: The package address
    """
    if domain == CONSTANTS.NETNA_DOMAIN:
        return CONSTANTS.NETNA_PACKAGE
    elif domain == CONSTANTS.TESTNET_DOMAIN:
        return CONSTANTS.TESTNET_PACKAGE
    else:
        return CONSTANTS.MAINNET_PACKAGE


async def get_current_server_time(
    throttler: Optional[Any] = None,
    domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> float:
    """
    Get current server time.

    Since Decibel is blockchain-based (Aptos), we use local time.
    Blockchain timestamps are validated on-chain, not via REST API.

    :param throttler: The rate limiter (unused, for compatibility)
    :param domain: The domain (unused, for compatibility)
    :return: Current time in milliseconds
    """
    return time.time() * 1000
