import asyncio
from enum import Enum
import logging
from typing import Optional

from hummingbot.core.gateway import gateway_http_client

POLL_INTERVAL = 2.0
POLL_TIMEOUT = 1.0


class Status(Enum):
    ONLINE = 1
    OFFLINE = 2


class StatusMonitor:
    _monitor_task: Optional[asyncio.Task]
    _current_status: Status
    _sm_logger: Optional[logging.Logger] = None

    @classmethod
    def logger(cls) -> logging.Logger:
        if cls._sm_logger is None:
            cls._sm_logger = logging.getLogger(__name__)
        return cls._sm_logger

    def __init__(self):
        self._current_status = Status.OFFLINE
        self._monitor_task = None

    @property
    def current_status(self) -> Status:
        return self._current_status

    def start(self):
        self._monitor_task = asyncio.create_task(self._monitor_loop())

    def stop(self):
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            self._monitor_task = None

    async def _monitor_loop(self):
        while True:
            try:
                if await asyncio.wait_for(gateway_http_client.ping_gateway(), timeout=POLL_TIMEOUT):
                    self._current_status = Status.ONLINE
                else:
                    self._current_status = Status.OFFLINE
            except asyncio.CancelledError:
                raise
            except Exception:
                self._current_status = Status.OFFLINE
            await asyncio.sleep(POLL_INTERVAL)
