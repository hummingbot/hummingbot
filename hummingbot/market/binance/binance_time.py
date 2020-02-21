import aiohttp
import asyncio
from collections import deque
import logging
import statistics
import time
from typing import Dict, Deque

from hummingbot.logger import HummingbotLogger
from hummingbot.core.utils.async_utils import safe_ensure_future


class BinanceTime:
    """
    Used to monkey patch Binance client's time module to adjust request timestamp when needed
    """
    BINANCE_TIME_API = "https://api.binance.com/api/v1/time"
    _bt_logger = None
    _bt_shared_instance = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _bt_logger
        if _bt_logger is None:
            _bt_logger = logging.getLogger(__name__)
        return _bt_logger

    @classmethod
    def get_instance(cls) -> "BinanceTime":
        if cls._bt_shared_instance is None:
            cls._bt_shared_instance = BinanceTime()
        return cls._bt_shared_instance

    def __init__(self, check_interval: float = 60.0):
        self._time_offset_ms: Deque[float] = deque([])
        self._set_server_time_offset_task: asyncio.Task = None
        self._started: bool = False
        self._server_time_offset_check_interval = check_interval
        self._median_window = 5

    @property
    def started(self) -> bool:
        return self._started

    @property
    def time_offset_ms(self) -> float:
        if not self._time_offset_ms:
            return time.time() - time.perf_counter()
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

    async def update_server_time_offset_loop(self):
        while True:
            await self.update_server_time_offset()
            await asyncio.sleep(self._server_time_offset_check_interval)

    async def update_server_time_offset(self):
        try:
            local_before_ms: float = time.perf_counter() * 1e3
            async with aiohttp.ClientSession() as session:
                async with session.get(self.BINANCE_TIME_API) as resp:
                    resp_data: Dict[str, float] = await resp.json()
                    binance_server_time_ms: float = float(resp_data["serverTime"])
                    local_after_ms: float = time.perf_counter() * 1e3
            local_server_time_pre_image_ms: float = (local_before_ms + local_after_ms) / 2.0
            time_offset_ms: float = binance_server_time_ms - local_server_time_pre_image_ms
            self.add_time_offset_ms_sample(time_offset_ms)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().network(f"Error getting Binance server time.", exc_info=True,
                                  app_warning_msg=f"Could not refresh Binance server time. "
                                                  f"Check network connection.")
