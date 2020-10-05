#!/usr/bin/env python

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
from hummingbot.connector.exchange.loopring.loopring_api_order_book_data_source import LoopringAPIOrderBookDataSource
from hummingbot.connector.exchange.loopring.loopring_api_user_stream_data_source import LoopringAPIUserStreamDataSource
from hummingbot.connector.exchange.loopring.loopring_auth import LoopringAuth


class LoopringUserStreamTracker(UserStreamTracker):
    _krust_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._krust_logger is None:
            cls._krust_logger = logging.getLogger(__name__)
        return cls._krust_logger

    def __init__(self,
                 orderbook_tracker_data_source: LoopringAPIOrderBookDataSource,
                 loopring_auth: LoopringAuth):
        super().__init__()
        self._ev_loop: asyncio.events.AbstractEventLoop = asyncio.get_event_loop()
        self._data_source: Optional[UserStreamTrackerDataSource] = None
        self._user_stream_tracking_task: Optional[asyncio.Task] = None
        self._orderbook_tracker_data_source = orderbook_tracker_data_source
        self._loopring_auth: LoopringAuth = loopring_auth

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        if not self._data_source:
            self._data_source = LoopringAPIUserStreamDataSource(orderbook_tracker_data_source=self._orderbook_tracker_data_source,
                                                                loopring_auth=self._loopring_auth)
        return self._data_source

    @property
    def exchange_name(self) -> str:
        return "loopring"

    async def start(self):
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._ev_loop, self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
