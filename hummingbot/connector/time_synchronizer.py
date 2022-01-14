import asyncio
import logging
import statistics
import time

from collections import deque
from typing import Awaitable, Deque

from hummingbot.logger import HummingbotLogger


class TimeSynchronizer:
    """
    Used to synchronize the local time with the server's time.
    This class is useful when timestamp-based signatures are required by the exchange for authentication.
    Upon receiving a timestamped message from the server, use `update_server_time_offset_with_time_provider`
    to synchronize local time with the server's time.
    """

    NaN = float("nan")
    _logger = None

    def __init__(self):
        self._time_offset_ms: Deque[float] = deque(maxlen=5)

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @property
    def time_offset_ms(self) -> float:
        if not self._time_offset_ms:
            return (self._time() - self._current_seconds_counter()) * 1e3
        return statistics.median(self._time_offset_ms)

    def add_time_offset_ms_sample(self, offset: float):
        self._time_offset_ms.append(offset)

    def clear_time_offset_ms_samples(self):
        self._time_offset_ms.clear()

    def time(self) -> float:
        """
        Returns the current time in seconds calculated base on the deviation samples.
        :return: Calculated current time considering the registered deviations
        """
        return self._current_seconds_counter() + self.time_offset_ms * 1e-3

    async def update_server_time_offset_with_time_provider(self, time_provider: Awaitable):
        """
        Executes the time_provider passed as parameter to obtain the current time, and adds a new sample in the
        internal list.
        :param time_provider: Awaitable object that returns the current time
        """
        try:
            local_before_ms: float = self._current_seconds_counter() * 1e3
            server_time_ms: float = await time_provider
            local_after_ms: float = self._current_seconds_counter() * 1e3
            local_server_time_pre_image_ms: float = (local_before_ms + local_after_ms) / 2.0
            time_offset_ms: float = server_time_ms - local_server_time_pre_image_ms
            self.add_time_offset_ms_sample(time_offset_ms)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().network("Error getting server time.", exc_info=True,
                                  app_warning_msg="Could not refresh server time. Check network connection.")

    def _current_seconds_counter(self):
        return time.perf_counter()

    def _time(self):
        return time.time()
