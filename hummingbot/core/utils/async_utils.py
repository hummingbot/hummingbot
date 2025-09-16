"""
Async utilities for Hummingbot framework.
Minimal implementation to support connector development.
"""

import asyncio
from typing import Any, Awaitable, Optional


def safe_ensure_future(coro: Awaitable, loop: Optional[asyncio.AbstractEventLoop] = None) -> asyncio.Future:
    """
    Safely ensure a coroutine is scheduled as a future.
    
    Args:
        coro: The coroutine to schedule
        loop: Optional event loop to use
        
    Returns:
        Future object
    """
    if loop is None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    
    return asyncio.ensure_future(coro, loop=loop)


async def safe_gather(*coros, return_exceptions: bool = False) -> Any:
    """
    Safely gather multiple coroutines.
    
    Args:
        *coros: Coroutines to gather
        return_exceptions: Whether to return exceptions instead of raising
        
    Returns:
        Results from all coroutines
    """
    return await asyncio.gather(*coros, return_exceptions=return_exceptions)
