"""
Time Synchronizer for Coins.ph Exchange Connector

This module implements server time synchronization with the Coins.ph API
to ensure accurate timestamps for authenticated requests and prevent
authentication failures due to time drift.
"""

import asyncio
import logging
import time
from typing import Optional

import aiohttp

from hummingbot.connector.exchange.coinsxyz import coinsxyz_constants as CONSTANTS

# Production Hummingbot import
from hummingbot.connector.time_synchronizer import TimeSynchronizer


class CoinsxyzTimeSynchronizer(TimeSynchronizer):
    """
    Time synchronizer for Coins.ph API.

    This class manages time synchronization with the Coins.ph server to ensure
    accurate timestamps in authenticated requests. It periodically fetches the
    server time and calculates the offset between local and server time.
    """

    def __init__(self,
                 update_interval: float = 300.0,  # 5 minutes
                 max_time_diff_threshold: float = 30.0,  # 30 seconds
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        """
        Initialize the time synchronizer.

        :param update_interval: How often to sync with server (seconds)
        :param max_time_diff_threshold: Maximum acceptable time difference (seconds)
        :param domain: API domain to use
        """
        super().__init__()
        self._update_interval = update_interval
        self._max_time_diff_threshold = max_time_diff_threshold
        self._domain = domain
        self._logger = logging.getLogger(__name__)

        # Time synchronization state
        self._server_time_offset = 0.0  # Server time - local time
        self._last_sync_time = 0.0
        self._sync_task: Optional[asyncio.Task] = None
        self._is_syncing = False
        self._sync_lock = asyncio.Lock()

        # Statistics
        self._sync_count = 0
        self._sync_failures = 0
        self._last_sync_duration = 0.0
        self._time_drift_history = []

        # Build server time URL
        self._server_time_url = f"{CONSTANTS.REST_URL}{CONSTANTS.PUBLIC_API_VERSION}{CONSTANTS.SERVER_TIME_PATH_URL}"

    async def start(self):
        """Start the time synchronization service."""
        if self._sync_task is None or self._sync_task.done():
            self._logger.info("Starting Coins.ph time synchronizer")
            self._sync_task = asyncio.create_task(self._sync_loop())

            # Perform initial sync
            await self._sync_server_time()

    async def stop(self):
        """Stop the time synchronization service."""
        if self._sync_task and not self._sync_task.done():
            self._logger.info("Stopping Coins.ph time synchronizer")
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
            self._sync_task = None

    def time(self) -> float:
        """
        Get the current synchronized time.

        :return: Current time adjusted for server offset
        """
        local_time = time.time()
        return local_time + self._server_time_offset

    def get_server_time_offset(self) -> float:
        """
        Get the current server time offset.

        :return: Server time offset in seconds (server_time - local_time)
        """
        return self._server_time_offset

    def get_last_sync_time(self) -> float:
        """
        Get the timestamp of the last successful sync.

        :return: Last sync timestamp
        """
        return self._last_sync_time

    def get_sync_statistics(self) -> dict:
        """
        Get synchronization statistics.

        :return: Dictionary with sync statistics
        """
        return {
            "sync_count": self._sync_count,
            "sync_failures": self._sync_failures,
            "last_sync_time": self._last_sync_time,
            "last_sync_duration": self._last_sync_duration,
            "server_time_offset": self._server_time_offset,
            "time_drift_history": self._time_drift_history[-10:],  # Last 10 measurements
            "is_syncing": self._is_syncing,
            "success_rate": (self._sync_count / max(self._sync_count + self._sync_failures, 1)) * 100
        }

    def is_time_synchronized(self) -> bool:
        """
        Check if time is properly synchronized.

        :return: True if time is synchronized within acceptable threshold
        """
        if self._last_sync_time == 0:
            return False

        # Check if sync is recent enough
        time_since_sync = time.time() - self._last_sync_time
        if time_since_sync > self._update_interval * 2:  # Allow 2x interval before considering stale
            return False

        # Check if offset is within acceptable range
        return abs(self._server_time_offset) <= self._max_time_diff_threshold

    async def _sync_loop(self):
        """Main synchronization loop."""
        while True:
            try:
                await asyncio.sleep(self._update_interval)
                await self._sync_server_time()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in time sync loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying

    async def _sync_server_time(self):
        """Synchronize with server time."""
        if self._is_syncing:
            return  # Avoid concurrent syncs

        async with self._sync_lock:
            self._is_syncing = True
            sync_start_time = time.time()

            try:
                server_time = await self._fetch_server_time()
                if server_time:
                    await self._update_time_offset(server_time, sync_start_time)
                    self._sync_count += 1
                    self._logger.debug(f"Time sync successful. Offset: {self._server_time_offset:.3f}s")
                else:
                    self._sync_failures += 1
                    self._logger.warning("Failed to fetch server time")

            except Exception as e:
                self._sync_failures += 1
                self._logger.error(f"Time synchronization failed: {e}")
            finally:
                self._is_syncing = False
                self._last_sync_duration = time.time() - sync_start_time

    async def _fetch_server_time(self) -> Optional[float]:
        """
        Fetch server time from Coins.ph API.

        :return: Server timestamp in seconds, or None if failed
        """
        try:
            timeout = aiohttp.ClientTimeout(total=10.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                request_time = time.time()

                async with session.get(self._server_time_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        server_time_ms = data.get("serverTime")

                        if server_time_ms:
                            response_time = time.time()
                            # Adjust for network latency (rough estimate)
                            network_latency = (response_time - request_time) / 2
                            server_time_seconds = (server_time_ms / 1000.0) - network_latency

                            self._logger.debug(f"Server time: {server_time_ms}ms, "
                                               f"Network latency: {network_latency:.3f}s")
                            return server_time_seconds
                        else:
                            self._logger.warning("Server time response missing serverTime field")
                    else:
                        self._logger.warning(f"Server time request failed: HTTP {response.status}")

        except asyncio.TimeoutError:
            self._logger.warning("Server time request timed out")
        except Exception as e:
            self._logger.error(f"Error fetching server time: {e}")

        return None

    async def _update_time_offset(self, server_time: float, sync_start_time: float):
        """
        Update the time offset based on server time.

        :param server_time: Server timestamp in seconds
        :param sync_start_time: Local time when sync started
        """
        # Use the middle of the sync period for more accurate offset calculation
        sync_duration = time.time() - sync_start_time
        local_time_estimate = sync_start_time + (sync_duration / 2)

        new_offset = server_time - local_time_estimate

        # Smooth the offset to avoid sudden jumps
        if self._server_time_offset == 0.0:
            # First sync - use the new offset directly
            self._server_time_offset = new_offset
        else:
            # Apply exponential smoothing
            smoothing_factor = 0.3
            self._server_time_offset = (smoothing_factor * new_offset +
                                        (1 - smoothing_factor) * self._server_time_offset)

        # Track time drift history
        self._time_drift_history.append({
            "timestamp": time.time(),
            "offset": new_offset,
            "smoothed_offset": self._server_time_offset,
            "sync_duration": sync_duration
        })

        # Keep only recent history
        if len(self._time_drift_history) > 100:
            self._time_drift_history = self._time_drift_history[-50:]

        self._last_sync_time = time.time()

        # Log significant time differences
        if abs(new_offset) > self._max_time_diff_threshold:
            self._logger.warning(f"Large time difference detected: {new_offset:.3f}s "
                                 f"(threshold: {self._max_time_diff_threshold}s)")

        # Log drift changes
        if len(self._time_drift_history) > 1:
            prev_offset = self._time_drift_history[-2]["offset"]
            drift_change = abs(new_offset - prev_offset)
            if drift_change > 1.0:  # More than 1 second change
                self._logger.info(f"Time drift change detected: {drift_change:.3f}s")

    async def force_sync(self) -> bool:
        """
        Force an immediate time synchronization.

        :return: True if sync was successful, False otherwise
        """
        self._logger.info("Forcing time synchronization")
        sync_count_before = self._sync_count
        await self._sync_server_time()
        return self._sync_count > sync_count_before

    def validate_timestamp(self, timestamp: float, tolerance: float = 60.0) -> bool:
        """
        Validate if a timestamp is within acceptable range of server time.

        :param timestamp: Timestamp to validate (seconds)
        :param tolerance: Acceptable time difference (seconds)
        :return: True if timestamp is valid
        """
        current_server_time = self.time()
        time_diff = abs(timestamp - current_server_time)

        is_valid = time_diff <= tolerance

        if not is_valid:
            self._logger.warning(f"Timestamp validation failed: "
                                 f"diff={time_diff:.3f}s, tolerance={tolerance}s")

        return is_valid

    def get_synchronized_timestamp_ms(self) -> int:
        """
        Get current synchronized timestamp in milliseconds.

        :return: Current synchronized timestamp in milliseconds
        """
        return int(self.time() * 1000)

    def time_ms(self) -> int:
        """
        Get current synchronized time in milliseconds.

        :return: Current time in milliseconds
        """
        return int(self.time() * 1000)

    def get_timestamp(self) -> int:
        """
        Get current synchronized timestamp in milliseconds.

        :return: Current timestamp in milliseconds
        """
        return int(self.time() * 1000)

    def get_time_offset_ms(self) -> float:
        """
        Get server time offset in milliseconds.

        :return: Server time offset in milliseconds
        """
        return self._server_time_offset * 1000

    # Day 18: Additional Timestamp Drift Methods

    async def detect_timestamp_drift(self) -> dict:
        """
        Detect timestamp drift - Day 18 Implementation.

        Returns:
            Dictionary with drift detection results
        """
        try:
            # Get current server time
            server_time = await self._fetch_server_time()
            local_time = time.time()

            # Calculate drift
            drift_seconds = abs(server_time - local_time)
            drift_ms = drift_seconds * 1000

            # Determine severity
            if drift_ms < 100:
                severity = "none"
            elif drift_ms < 500:
                severity = "low"
            elif drift_ms < 1000:
                severity = "medium"
            elif drift_ms < 5000:
                severity = "high"
            else:
                severity = "critical"

            result = {
                'drift_ms': drift_ms,
                'drift_seconds': drift_seconds,
                'severity': severity,
                'server_time': server_time,
                'local_time': local_time,
                'correction_needed': drift_ms > 500,
                'threshold_exceeded': drift_seconds > self._max_time_diff_threshold
            }

            if result['correction_needed']:
                self._logger.warning(f"Timestamp drift detected: {drift_ms:.1f}ms ({severity})")

            return result

        except Exception as e:
            self._logger.error(f"Error detecting timestamp drift: {e}")
            return {
                'error': str(e),
                'drift_ms': 0,
                'severity': 'unknown',
                'correction_needed': False
            }

    async def correct_timestamp_drift(self, drift_info: dict = None) -> bool:
        """
        Correct timestamp drift - Day 18 Implementation.

        Args:
            drift_info: Optional drift information from detect_timestamp_drift

        Returns:
            True if correction was successful
        """
        try:
            # Get drift info if not provided
            if drift_info is None:
                drift_info = await self.detect_timestamp_drift()

            if 'error' in drift_info:
                return False

            if not drift_info.get('correction_needed', False):
                self._logger.debug("No timestamp correction needed")
                return True

            # Apply correction
            server_time = drift_info['server_time']
            local_time = drift_info['local_time']
            new_offset = server_time - local_time

            # Update offset
            self._server_time_offset = new_offset
            self._last_sync_time = time.time()

            self._logger.info(f"Applied timestamp correction: {new_offset:.3f}s offset")
            return True

        except Exception as e:
            self._logger.error(f"Error correcting timestamp drift: {e}")
            return False

    async def sync_with_server_time(self, force: bool = False) -> bool:
        """
        Synchronize with server time - Day 18 Implementation.

        Args:
            force: Force synchronization even if recently synced

        Returns:
            True if synchronization was successful
        """
        try:
            current_time = time.time()

            # Check if sync is needed
            if not force and (current_time - self._last_sync_time) < self._update_interval:
                self._logger.debug("Time sync not needed - recently synchronized")
                return True

            self._logger.info("Synchronizing with server time")

            # Detect and correct drift
            drift_info = await self.detect_timestamp_drift()
            success = await self.correct_timestamp_drift(drift_info)

            if success:
                self._logger.info("Time synchronization completed successfully")
            else:
                self._logger.error("Time synchronization failed")

            return success

        except Exception as e:
            self._logger.error(f"Error synchronizing with server time: {e}")
            return False
