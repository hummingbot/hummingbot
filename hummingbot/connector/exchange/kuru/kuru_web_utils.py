"""
Minimal web utilities for the Kuru connector.

Most operations go through the Kuru SDK directly. This helper
is provided for compatibility with Hummingbot's ExchangePyBase.
"""

import time


async def get_current_server_time(**kwargs) -> float:
    """DEX connector - no server time sync needed."""
    return time.time()
