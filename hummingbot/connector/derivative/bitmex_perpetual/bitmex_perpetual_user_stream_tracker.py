import asyncio
import logging
from typing import Optional

import hummingbot.connector.derivative.bitmex_perpetual.constants as CONSTANTS
from hummingbot.connector.derivative.bitmex_perpetual.bitmex_perpetual_auth import BitmexPerpetualAuth
from hummingbot.connector.derivative.bitmex_perpetual.bitmex_perpetual_user_stream_data_source import (
    BitmexPerpetualUserStreamDataSource,
)
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger


class BitmexPerpetualUserStreamTracker(UserStreamTracker):

    _bpust_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bust_logger is None:
            cls._bust_logger = logging.getLogger(__name__)
        return cls._bust_logger

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        return AsyncThrottler(CONSTANTS.RATE_LIMITS)

    def __init__(self,
                 auth: BitmexPerpetualAuth,
                 domain: str = CONSTANTS.DOMAIN,
                 throttler: Optional[AsyncThrottler] = None,
                 api_factory: Optional[WebAssistantsFactory] = None,
                 time_synchronizer: Optional[TimeSynchronizer] = None):
        self._data_source: Optional[UserStreamTrackerDataSource] = None
        self._auth: BitmexPerpetualAuth = auth
        self._domain = domain
        self._throttler = throttler
        self._api_factory = api_factory
        self._time_synchronizer = time_synchronizer

        super().__init__(self.data_source)
        self._ev_loop: asyncio.events.AbstractEventLoop = asyncio.get_event_loop()
        self._user_stream_tracking_task: Optional[asyncio.Task] = None

    @property
    def exchange_name(self) -> str:
        return self._domain

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        if self._data_source is None:
            self._data_source = BitmexPerpetualUserStreamDataSource(
                auth=self._auth,
                domain=self._domain,
                throttler=self._throttler,
                api_factory=self._api_factory,
                time_synchronizer=self._time_synchronizer)
        return self._data_source

    async def start(self):
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._ev_loop, self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
