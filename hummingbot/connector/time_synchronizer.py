import asyncio
import logging
import time
from collections import deque
from typing import Awaitable, Deque

import numpy

from hummingbot.logger import HummingbotLogger


class TimeSynchronizer:
    """
    Used to synchronize the local time with the server's time.
    This class is useful when timestamp-based signatures are required by the exchange for authentication.
    Upon receiving a timestamped message from the server, use `update_server_time_offset_with_time_provider`
    to synchronize local time with the server's time.
    """

    _logger = None

    def __init__(self):
        self._time_offset_ms: Deque[float] = deque(maxlen=5)
        self._time_reference_s = self._time()
        self._counter_reference_ns: int = time.monotonic_ns()

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @property
    def time_offset_ms(self) -> float:
        if not self._time_offset_ms:
            offset = (self._time() - self._current_precise_time_s()) * 1e3
        else:
            median = numpy.median(self._time_offset_ms)
            weighted_average = numpy.average(self._time_offset_ms,
                                             weights=range(1, len(self._time_offset_ms) * 2 + 1, 2))
            offset = numpy.mean([median, weighted_average])

        return offset

    def add_time_offset_ms_sample(self, offset: float):
        self._time_offset_ms.append(offset)

    def clear_time_offset_ms_samples(self):
        self._time_offset_ms.clear()

    def time(self) -> float:
        """
        Returns the current time in seconds calculated base on the deviation samples.
        :return: Calculated current time considering the registered deviations
        """
        return self._current_precise_time_s() + self.time_offset_ms * 1e-3

    async def update_server_time_offset_with_time_provider(self, time_provider: Awaitable):
        """
        Executes the time_provider passed as parameter to obtain the current time, and adds a new sample in the
        internal list.

        :param time_provider: Awaitable object that returns the current time in milliseconds
        """
        try:
            local_before_ns: int = self._current_precise_time_ns()
            server_time_ms: float = await time_provider
            local_after_ns: int = self._current_precise_time_ns()
            local_time_ms: float = (local_before_ns + local_after_ns) * 0.5 * 1e-6

            # Verify server time in milliseconds
            time_ratio = server_time_ms / local_time_ms
            if not (0.01 <= time_ratio <= 100.0):
                raise ValueError("Server time does not appear to be within 2 orders of magnitude of local time.")

            time_offset_ms: float = server_time_ms - local_time_ms
            self.add_time_offset_ms_sample(time_offset_ms)
        except (asyncio.CancelledError, ValueError):
            raise
        except Exception:
            self.logger().network("Error getting server time.", exc_info=True,
                                  app_warning_msg="Could not refresh server time. Check network connection.")

    async def update_server_time_if_not_initialized(self, time_provider: Awaitable):
        """
        Executes the time_provider passed as parameter to obtain the current time, and adds a new sample in the
        internal list, ONLY if the current instance has not been updated yet.

        :param time_provider: Awaitable object that returns the current time
        """
        if not self._time_offset_ms:
            await self.update_server_time_offset_with_time_provider(time_provider)
        else:
            # Avoid warning for async without awaited function
            await asyncio.sleep(0)

    def _elapsed_precise_ns(self) -> int:
        return time.monotonic_ns() - self._counter_reference_ns

    def _current_precise_time_ns(self) -> int:
        return int(self._time_reference_s * 1e9) + self._elapsed_precise_ns()

    def _current_precise_time_s(self) -> float:
        return self._time_reference_s + self._elapsed_precise_ns() * 1e-9

    @staticmethod
    def _time():
        return time.time()
