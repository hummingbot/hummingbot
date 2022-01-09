import asyncio
import logging

from typing import Optional

from hummingbot.connector.exchange.binance.binance_api_user_stream_data_source import BinanceAPIUserStreamDataSource
from hummingbot.connector.exchange.binance.binance_auth import BinanceAuth
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.logger import HummingbotLogger


class BinanceUserStreamTracker(UserStreamTracker):
    _logger: Optional[HummingbotLogger] = None

    def __init__(self, auth: BinanceAuth, domain: str = "com", throttler: Optional[AsyncThrottler] = None):
        super().__init__()
        self._auth: BinanceAuth = auth
        self._ev_loop: asyncio.events.AbstractEventLoop = asyncio.get_event_loop()
        self._data_source: Optional[UserStreamTrackerDataSource] = None
        self._user_stream_tracking_task: Optional[asyncio.Task] = None
        self._domain = domain
        self._throttler = throttler

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        """
        Returns the instance of the data source that listens to the private user channel to receive updates from the
        exchange. If the instance is not initialized it will be created.
        :return: the user stream instance that is listening to user updates from the server using the private channel
        """
        if not self._data_source:
            self._data_source = BinanceAPIUserStreamDataSource(auth=self._auth, domain=self._domain, throttler=self._throttler)
        return self._data_source

    async def start(self):
        """
        Starts the background task that connects to the exchange and listens to user activity updates
        """
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._ev_loop, self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
