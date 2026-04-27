import logging
from typing import Optional

import aiohttp

from hummingbot.connector.derivative.lighter_perpetual import lighter_perpetual_constants as perp_constants
from hummingbot.connector.exchange.lighter import lighter_constants as spot_constants


def _get_base_url(connector_name: str) -> str:
    connector_name = connector_name or ""
    is_perpetual = connector_name in {"lighter_perpetual", "lighter_perpetual_testnet"}
    is_testnet = connector_name in {"lighter_testnet", "lighter_perpetual_testnet"}

    if is_perpetual:
        return perp_constants.TESTNET_REST_URL if is_testnet else perp_constants.REST_URL
    return spot_constants.TESTNET_REST_URL if is_testnet else spot_constants.REST_URL


async def fetch_lighter_public_key(connector_name: str, account_index: str, api_key_index: str) -> Optional[str]:
    """Fetch the public key for a lighter API key from the exchange REST API.

    Returns the public key hex string, or None if the lookup fails.
    """
    logger = logging.getLogger(__name__)
    url = f"{_get_base_url(connector_name)}/apikeys"
    params = {"account_index": account_index, "api_key_index": api_key_index}

    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    api_keys = data.get("api_keys", [])
                    if api_keys:
                        return api_keys[0].get("public_key")
                    logger.warning(
                        "fetch_lighter_public_key: no api_keys in response "
                        f"(account={account_index}, key_index={api_key_index}): {data}"
                    )
                else:
                    logger.warning(
                        f"fetch_lighter_public_key: HTTP {resp.status} "
                        f"(account={account_index}, key_index={api_key_index})"
                    )
    except Exception as e:
        logger.warning(f"fetch_lighter_public_key failed: {e}")

    return None


async def validate_lighter_api_key_index(connector_name: str, account_index: str, api_key_index: str) -> Optional[str]:
    """Validate that api_key_index exists within the given account.

    Returns None if the key is valid (or if the check cannot be performed due to a network error).
    Returns an error message string if the key index is not found in the account.
    """
    url = f"{_get_base_url(connector_name)}/apikeys"
    params = {"account_index": account_index, "api_key_index": api_key_index}

    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if not data.get("api_keys"):
                        return (
                            f"No API key found at index {api_key_index} for account {account_index}. "
                            "Please verify your API key index."
                        )
    except Exception:
        pass

    return None
