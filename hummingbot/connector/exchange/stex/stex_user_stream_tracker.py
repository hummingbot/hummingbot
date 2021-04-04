import asyncio
import logging
from typing import (
    Optional
)
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.connector.exchange.stex.stex_api_user_stream_data_source import StexAPIUserStreamDataSource
from hummingbot.connector.exchange.stex.stex_auth import StexAuth

class StexUserStreamTracker(UserStreamTracker):
    _stust_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._stust_logger is None:
            cls._stust_logger = logging.getLogger(__name__)
        return cls._stust_logger

    def __init__(self,
                 stex_auth: StexAuth):
        super().__init__()
        self._ev_loop: asyncio.events.AbstractEventLoop = asyncio.get_event_loop()
        self._data_source: Optional[UserStreamTrackerDataSource] = None
        self._user_stream_tracking_task: Optional[asyncio.Task] = None
        self._stex_auth: StexAuth = stex_auth

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        if not self._data_source:
            self._data_source = StexAPIUserStreamDataSource(stex_auth=self._stex_auth)
        return self._data_source

    def exchange_name(self) -> str:
        return "stex"

    async def start(self):
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._ev_loop, self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
