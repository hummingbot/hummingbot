import aiohttp
import asyncio
import logging
import statistics
import time
import dateutil.parser
from collections import deque
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.logger import HummingbotLogger
from hummingbot.core.utils.async_utils import safe_ensure_future


class OpenwareTime:
    """
    Used to monkey patch Openware client's time module to adjust request timestamp when needed
    """
    _bt_logger = None
    _bt_shared_instance = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bt_logger is None:
            cls._bt_logger = logging.getLogger(__name__)
        return cls._bt_logger

    @classmethod
    def get_instance(cls) -> "OpenwareTime":
        if cls._bt_shared_instance is None:
            cls._bt_shared_instance = OpenwareTime()
        return cls._bt_shared_instance

    def __init__(self, check_interval: float = 60.0):
        self._time_offset_ms = deque([])
        self._set_server_time_offset_task = None
        self._started = False
        self.SERVER_TIME_OFFSET_CHECK_INTERVAL = check_interval
        self.median_window = 100

    @property
    def started(self):
        return self._started

    @property
    def time_offset_ms(self):
        if not self._time_offset_ms:
            return 0.0
        return statistics.median(self._time_offset_ms)

    def set_time_offset_ms(self, offset):
        self._time_offset_ms.append(offset)
        if len(self._time_offset_ms) > self.median_window:
            self._time_offset_ms.popleft()

    def time(self):
        return time.time() + self.time_offset_ms * 1e-3

    def start(self):
        if self._set_server_time_offset_task is None:
            self._set_server_time_offset_task = safe_ensure_future(self.set_server_time_offset())
            self._started = True

    def stop(self):
        if self._set_server_time_offset_task:
            self._set_server_time_offset_task.cancel()
            self._set_server_time_offset_task = None
            self._time_offset_ms.clear()
            self._started = False

    async def set_server_time_offset(self):
        while True:
            # try:
            async with aiohttp.ClientSession() as session:
                api_url = global_config_map.get("openware_api_url").value
                uri = "%s/public/timestamp" % api_url
                async with session.get(uri) as resp:
                    time_now_ms = time.time() * 1e3
                    openware_server_time = dateutil.parser.parse((await resp.text()).replace('"', '')).timestamp() * 1e3
                    time_after_ms = time.time() * 1e3
            expected_server_time = int((time_after_ms + time_now_ms) // 2)
            time_offset = openware_server_time - expected_server_time
            self.set_time_offset_ms(time_offset)

            # except asyncio.CancelledError:
            #    raise
            # except Exception:
            #    self.logger().network(f"Error getting Openware server time.", exc_info=True,
            #                          app_warning_msg=f"Could not refresh Openware server time. "
            #                                          f"Check network connection.")

            await asyncio.sleep(self.SERVER_TIME_OFFSET_CHECK_INTERVAL)
