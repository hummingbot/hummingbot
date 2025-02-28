import asyncio
import logging
from typing import Optional

from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger


class NotifierBase:
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self):
        self._started = False
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._send_message_task: Optional[asyncio.Task] = None

    def add_message_to_queue(self, message: str):
        self._message_queue.put_nowait(message)

    def start(self):
        if self._send_message_task is None:
            self._send_message_task = safe_ensure_future(self.send_message_from_queue())

    def stop(self):
        if self._send_message_task:
            self._send_message_task.cancel()
            self._send_message_task = None

    async def send_message_from_queue(self):
        while True:
            try:
                new_msg: str = await self._message_queue.get()
                if isinstance(new_msg, str) and len(new_msg) > 0:
                    await self._send_message(new_msg)
            except Exception as e:
                self.logger().error(str(e))
            except asyncio.CancelledError:
                raise
            await self._sleep(1.0)

    async def _sleep(self, seconds: float):
        await asyncio.sleep(seconds)

    async def _send_message(self, message: str):
        """
        A
        """
        raise NotImplementedError
