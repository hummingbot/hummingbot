#!/usr/bin/env python

import asyncio
import aiohttp
import logging

from typing import (
    Optional,
    List,
)
from hummingbot.connector.exchange.ascend_ex.ascend_ex_api_user_stream_data_source import \
    AscendExAPIUserStreamDataSource
from hummingbot.connector.exchange.ascend_ex.ascend_ex_auth import AscendExAuth
from hummingbot.connector.exchange.ascend_ex import ascend_ex_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.data_type.user_stream_tracker import (
    UserStreamTracker
)
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)

from hummingbot.logger import HummingbotLogger


class AscendExUserStreamTracker(UserStreamTracker):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 shared_client: Optional[aiohttp.ClientSession] = None,
                 throttler: Optional[AsyncThrottler] = None,
                 ascend_ex_auth: Optional[AscendExAuth] = None,
                 trading_pairs: Optional[List[str]] = None):
        super().__init__()
        self._shared_client = shared_client
        self._throttler = throttler
        self._ascend_ex_auth: AscendExAuth = ascend_ex_auth
        self._trading_pairs: List[str] = trading_pairs or []
        self._ev_loop: asyncio.events.AbstractEventLoop = asyncio.get_event_loop()
        self._data_source: Optional[UserStreamTrackerDataSource] = None
        self._user_stream_tracking_task: Optional[asyncio.Task] = None

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        """
        *required
        Initializes a user stream data source (user specific order diffs from live socket stream)
        :return: OrderBookTrackerDataSource
        """
        if not self._data_source:
            self._data_source = AscendExAPIUserStreamDataSource(
                shared_client=self._shared_client,
                throttler=self._throttler,
                ascend_ex_auth=self._ascend_ex_auth,
                trading_pairs=self._trading_pairs
            )
        return self._data_source

    @property
    def exchange_name(self) -> str:
        """
        *required
        Name of the current exchange
        """
        return CONSTANTS.EXCHANGE_NAME

    async def start(self):
        """
        *required
        Start all listeners and tasks
        """
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._ev_loop, self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
