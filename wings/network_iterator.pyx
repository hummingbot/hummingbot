# distutils: language=c++

import asyncio
from enum import Enum
import logging
from typing import Optional

from .clock cimport Clock

NaN = float("nan")
s_logger = None

class NetworkStatus(Enum):
    STOPPED = 0
    NOT_CONNECTED = 1
    CONNECTED = 2



cdef class NetworkIterator(TimeIterator):
    @classmethod
    def logger(cls) -> logging.Logger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self):
        super().__init__()
        self._network_status = NetworkStatus.STOPPED
        self._last_connected_timestamp = NaN
        self._check_network_interval = 10.0
        self._check_network_timeout = 5.0
        self._network_error_wait_time = 60.0
        self._check_network_task = None

    @property
    def network_status(self) -> NetworkStatus:
        return self._network_status

    @property
    def last_connected_timestamp(self) -> float:
        return self._last_connected_timestamp

    @property
    def check_network_task(self) -> Optional[asyncio.Task]:
        return self._check_network_task

    @property
    def check_network_interval(self) -> float:
        return self._check_network_interval

    @check_network_interval.setter
    def check_network_interval(self, double interval):
        self._check_network_interval = interval

    @property
    def network_error_wait_time(self) -> float:
        return self._network_error_wait_time

    @network_error_wait_time.setter
    def network_error_wait_time(self, double wait_time):
        self._network_error_wait_time = wait_time

    @property
    def check_network_timeout(self) -> float:
        return self._check_network_timeout

    @check_network_timeout.setter
    def check_network_timeout(self, double timeout):
        self._check_network_timeout = timeout

    async def start_network(self):
        pass

    async def stop_network(self):
        pass

    async def check_network(self) -> NetworkStatus:
        self.logger().warning("check_network() has not been implemented!")
        return NetworkStatus.NOT_CONNECTED

    async def _check_network_loop(self):
        while True:
            new_status = self._network_status

            try:
                new_status = await asyncio.wait_for(self.check_network(), timeout=self._check_network_timeout)
            except asyncio.CancelledError:
                raise
            except asyncio.TimeoutError:
                self.logger().debug(f"Check network call has timed out. Network status is not connected.")
                new_status = NetworkStatus.NOT_CONNECTED
            except Exception:
                self.logger().error("Unexpected error while checking for network status.", exc_info=True)
                await asyncio.sleep(self._network_error_wait_time)
                continue

            if new_status != self._network_status:
                self.logger().info(f"Network status has changed to {new_status}.")
            self._network_status = new_status

            await asyncio.sleep(self._check_network_interval)

    cdef c_start(self, Clock clock, double timestamp):
        TimeIterator.c_start(self, clock, timestamp)
        self._check_network_task = asyncio.ensure_future(self._check_network_loop())
        asyncio.ensure_future(self.start_network())

    cdef c_stop(self, Clock clock):
        TimeIterator.c_stop(self, clock)
        asyncio.ensure_future(self.stop_network())
        if self._check_network_task is not None:
            self._check_network_task.cancel()
            self._check_network_task = None
        self._network_status = NetworkStatus.STOPPED
