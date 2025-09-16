"""
Async throttler for API rate limiting.
Minimal implementation to support connector development.
"""

import asyncio
import time
from typing import Dict, List, Optional
from .data_types import RateLimit


class AsyncThrottler:
    """
    Async throttler for managing API rate limits.
    """
    
    def __init__(self, rate_limits: List[RateLimit]):
        """
        Initialize the throttler.
        
        Args:
            rate_limits: List of rate limit configurations
        """
        self._rate_limits: Dict[str, RateLimit] = {rl.limit_id: rl for rl in rate_limits}
        self._request_times: Dict[str, List[float]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        
        for limit_id in self._rate_limits:
            self._request_times[limit_id] = []
            self._locks[limit_id] = asyncio.Lock()
    
    async def acquire_token(self, limit_id: str) -> None:
        """
        Acquire a token for the specified rate limit.
        
        Args:
            limit_id: The rate limit identifier
        """
        if limit_id not in self._rate_limits:
            return
        
        rate_limit = self._rate_limits[limit_id]
        
        async with self._locks[limit_id]:
            current_time = time.time()
            request_times = self._request_times[limit_id]
            
            # Remove old requests outside the time window
            cutoff_time = current_time - rate_limit.time_interval
            self._request_times[limit_id] = [t for t in request_times if t > cutoff_time]
            
            # Check if we need to wait
            if len(self._request_times[limit_id]) >= rate_limit.limit:
                # Calculate wait time
                oldest_request = min(self._request_times[limit_id])
                wait_time = rate_limit.time_interval - (current_time - oldest_request)
                
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    current_time = time.time()
            
            # Add current request
            self._request_times[limit_id].append(current_time)
    
    async def execute_task(self, limit_id: str, task) -> any:
        """
        Execute a task with rate limiting.
        
        Args:
            limit_id: The rate limit identifier
            task: The task to execute
            
        Returns:
            Task result
        """
        await self.acquire_token(limit_id)
        return await task
