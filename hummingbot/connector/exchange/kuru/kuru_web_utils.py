"""
Minimal web utilities for the Kuru connector.

Most operations go through the Kuru SDK directly. These helpers
are provided for compatibility with Hummingbot's ExchangePyBase
and for auxiliary REST calls to the Kuru API.
"""

import time
from typing import Optional

import aiohttp


async def get_current_server_time(**kwargs) -> float:
    """DEX connector - no server time sync needed."""
    return time.time()


async def api_request(
    method: str,
    url: str,
    params: Optional[dict] = None,
    data: Optional[dict] = None,
    headers: Optional[dict] = None,
) -> dict:
    """
    Simple async HTTP request helper.

    Args:
        method: HTTP method (GET, POST, etc.)
        url: Full URL
        params: Query parameters
        data: JSON body
        headers: HTTP headers

    Returns:
        Parsed JSON response
    """
    async with aiohttp.ClientSession() as session:
        async with session.request(
            method=method,
            url=url,
            params=params,
            json=data,
            headers=headers,
        ) as response:
            response.raise_for_status()
            return await response.json()


async def get_active_orders(
    api_url: str,
    user_address: str,
    market_address: str,
) -> list[dict]:
    """
    Fetch active orders for a user from the Kuru REST API.

    Args:
        api_url: Kuru API base URL
        user_address: Wallet address
        market_address: Market contract address

    Returns:
        List of active order dicts
    """
    url = f"{api_url}/api/v2/{user_address}/user/orders/active/{market_address}?limit=100"
    try:
        response = await api_request("GET", url)
        orders = response.get("data", {}).get("orders", [])
        return orders if orders else []
    except Exception:
        return []


async def get_market_info(api_url: str, market_address: str) -> dict:
    """
    Fetch market info from the Kuru REST API.

    Args:
        api_url: Kuru API base URL
        market_address: Market contract address

    Returns:
        Market info dict
    """
    url = f"{api_url}/api/v2/market/{market_address}"
    return await api_request("GET", url)
