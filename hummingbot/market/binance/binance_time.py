import aiohttp
import asyncio
import logging
import time
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
        self._time_offset_ms = 0.0
        self._set_server_time_offset_task = None
        self._started = False
        self.SERVER_TIME_OFFSET_CHECK_INTERVAL = check_interval

    @property
    def started(self):
        return self._started

    @property
    def time_offset_ms(self):
        return self._time_offset_ms

    def time(self):
        return time.time() + self.time_offset_ms * 1e-3

    def start(self):
        if self._set_server_time_offset_task is None:
            self._set_server_time_offset_task = safe_ensure_future(self.set_server_time_offset_loop())
            self._started = True

    def stop(self):
        if self._set_server_time_offset_task:
            self._set_server_time_offset_task.cancel()
            self._set_server_time_offset_task = None
            self._time_offset_ms = 0.0
            self._started = False

    async def set_server_time_offset_loop(self):
        while True:
            await self.set_server_time_offset()
            await asyncio.sleep(self.SERVER_TIME_OFFSET_CHECK_INTERVAL)

    async def set_server_time_offset(self):
        try:
            time_now_ms = time.time() * 1e3
            async with aiohttp.ClientSession() as session:
                async with session.get(self.BINANCE_TIME_API) as resp:
                    resp_data = await resp.json()
                    binance_server_time = resp_data["serverTime"]
            time_after_ms = time.time() * 1e3
            expected_server_time = int((time_after_ms + time_now_ms) // 2)
            self._time_offset_ms = binance_server_time - expected_server_time
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().network(f"Error getting Binance server time.", exc_info=True,
                                  app_warning_msg=f"Could not refresh Binance server time. "
                                                  f"Check network connection.")
