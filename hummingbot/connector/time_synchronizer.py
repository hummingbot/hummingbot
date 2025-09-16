"""
Time synchronizer for Hummingbot connectors.
Minimal implementation to support connector development.
"""

import time
from typing import Optional


class TimeSynchronizer:
    """
    Time synchronizer for keeping track of server time offset.
    """
    
    def __init__(self):
        self._time_offset_ms: float = 0.0
        self._last_update_timestamp: float = 0.0
    
    def update_server_time_offset_with_time_provider(self, time_provider_fn) -> None:
        """
        Update server time offset using a time provider function.
        
        Args:
            time_provider_fn: Function that returns server time in milliseconds
        """
        try:
            server_time_ms = time_provider_fn()
            local_time_ms = time.time() * 1000
            self._time_offset_ms = server_time_ms - local_time_ms
            self._last_update_timestamp = time.time()
        except Exception:
            # If we can't get server time, use local time
            self._time_offset_ms = 0.0
    
    def time(self) -> float:
        """
        Get current synchronized time in seconds.
        
        Returns:
            Current time in seconds
        """
        return time.time() + (self._time_offset_ms / 1000.0)
    
    def time_ms(self) -> int:
        """
        Get current synchronized time in milliseconds.
        
        Returns:
            Current time in milliseconds
        """
        return int((time.time() * 1000) + self._time_offset_ms)
    
    @property
    def time_offset_ms(self) -> float:
        """Get the current time offset in milliseconds."""
        return self._time_offset_ms

    def get_time_offset_ms(self) -> float:
        """Get the current time offset in milliseconds."""
        return self._time_offset_ms

    def get_timestamp(self) -> int:
        """Get current timestamp in milliseconds."""
        return self.time_ms()
