import asyncio
from collections import deque
import logging
import statistics
import time
from typing import Deque, Optional, Callable, Awaitable

from hummingbot.logger import HummingbotLogger
from hummingbot.core.utils.async_utils import safe_ensure_future


class TimePatcher:
    # BINANCE_TIME_API = "https://api.binance.com/api/v1/time"
    NaN = float("nan")
    _bt_logger = None
    _bt_shared_instance = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bt_logger is None:
            cls._bt_logger = logging.getLogger(__name__)
        return cls._bt_logger

    # query_time_func returns the server time in seconds
    def __init__(self, exchange_name: str, query_time_func: Callable[[], Awaitable[float]], check_interval: float = 60.0):
        self._exchange_name = exchange_name
        self._query_time_func = query_time_func
        self._time_offset_ms: Deque[float] = deque([])
        self._set_server_time_offset_task: Optional[asyncio.Task] = None
        self._started: bool = False
        self._server_time_offset_check_interval = check_interval
        self._median_window = 5
        self._last_update_local_time: float = self.NaN
        self._scheduled_update_task: Optional[asyncio.Task] = None

    @property
    def started(self) -> bool:
        return self._started

    @property
    def time_offset_ms(self) -> float:
        if not self._time_offset_ms:
            return (time.time() - time.perf_counter()) * 1e3
        return statistics.median(self._time_offset_ms)

    def add_time_offset_ms_sample(self, offset: float):
        self._time_offset_ms.append(offset)
        while len(self._time_offset_ms) > self._median_window:
            self._time_offset_ms.popleft()

    def clear_time_offset_ms_samples(self):
        self._time_offset_ms.clear()

    def time(self) -> float:
        return time.perf_counter() + self.time_offset_ms * 1e-3

    def start(self):
        if self._set_server_time_offset_task is None:
            self._set_server_time_offset_task = safe_ensure_future(self.update_server_time_offset_loop())
            self._started = True

    def stop(self):
        if self._set_server_time_offset_task:
            self._set_server_time_offset_task.cancel()
            self._set_server_time_offset_task = None
            self._time_offset_ms.clear()
            self._started = False

    def schedule_update_server_time_offset(self) -> asyncio.Task:
        # If an update task is already scheduled, don't do anything.
        if self._scheduled_update_task is not None and not self._scheduled_update_task.done():
            return self._scheduled_update_task

        current_local_time: float = time.perf_counter()
        if not (current_local_time - self._last_update_local_time < 5):
            # If there was no recent update, schedule the server time offset update immediately.
            self._scheduled_update_task = safe_ensure_future(self.update_server_time_offset())
        else:
            # If there was a recent update, schedule the server time offset update after 5 seconds.
            async def update_later():
                await asyncio.sleep(5.0)
                await self.update_server_time_offset()
            self._scheduled_update_task = safe_ensure_future(update_later())

        return self._scheduled_update_task

    async def update_server_time_offset_loop(self):
        while True:
            await self.update_server_time_offset()
            await asyncio.sleep(self._server_time_offset_check_interval)

    async def update_server_time_offset(self):
        try:
            local_before_ms: float = time.perf_counter() * 1e3
            query_time_func = self._query_time_func.__func__
            server_time = await query_time_func()
            # async with aiohttp.ClientSession() as session:
            #     async with session.get(self.BINANCE_TIME_API) as resp:
            #         resp_data: Dict[str, float] = await resp.json()
            #         binance_server_time_ms: float = float(resp_data["serverTime"])
            #         local_after_ms: float = time.perf_counter() * 1e3
            local_after_ms: float = time.perf_counter() * 1e3
            local_server_time_pre_image_ms: float = (local_before_ms + local_after_ms) / 2.0
            time_offset_ms: float = server_time * 1000 - local_server_time_pre_image_ms
            self.add_time_offset_ms_sample(time_offset_ms)
            self._last_update_local_time = time.perf_counter()
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().network(f"Error getting {self._exchange_name} server time.", exc_info=True,
                                  app_warning_msg=f"Could not refresh {self._exchange_name} server time. "
                                                  "Check network connection.")
