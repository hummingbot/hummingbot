import asyncio
import logging
from typing import Optional

from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger


class UserStreamTracker:
    _ust_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._ust_logger is None:
            cls._ust_logger = logging.getLogger(__name__)
        return cls._ust_logger

    def __init__(self, data_source: UserStreamTrackerDataSource):
        self._user_stream: asyncio.Queue = asyncio.Queue()
        self._data_source = data_source
        self._user_stream_tracking_task: Optional[asyncio.Task] = None

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        return self._data_source

    @property
    def last_recv_time(self) -> float:
        return self.data_source.last_recv_time

    async def start(self):
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)

    @property
    def user_stream(self) -> asyncio.Queue:
        return self._user_stream
