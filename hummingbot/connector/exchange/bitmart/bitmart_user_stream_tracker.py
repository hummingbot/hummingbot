#!/usr/bin/env python

import asyncio
from typing import List, Optional

from hummingbot.connector.exchange.bitmart.bitmart_api_user_stream_data_source import BitmartAPIUserStreamDataSource
from hummingbot.connector.exchange.bitmart.bitmart_auth import BitmartAuth
from hummingbot.connector.exchange.bitmart.bitmart_constants import EXCHANGE_NAME
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class BitmartUserStreamTracker(UserStreamTracker):

    def __init__(self,
                 throttler: AsyncThrottler,
                 bitmart_auth: Optional[BitmartAuth] = None,
                 trading_pairs: Optional[List[str]] = [],
                 api_factory: Optional[WebAssistantsFactory] = None):
        super().__init__()
        self._api_factory = api_factory
        self._bitmart_auth: BitmartAuth = bitmart_auth
        self._trading_pairs: List[str] = trading_pairs
        self._ev_loop: asyncio.events.AbstractEventLoop = asyncio.get_event_loop()
        self._data_source: Optional[UserStreamTrackerDataSource] = None
        self._user_stream_tracking_task: Optional[asyncio.Task] = None
        self._throttler = throttler

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        """
        *required
        Initializes a user stream data source (user specific order diffs from live socket stream)
        :return: OrderBookTrackerDataSource
        """
        if not self._data_source:
            self._data_source = BitmartAPIUserStreamDataSource(
                throttler=self._throttler,
                bitmart_auth=self._bitmart_auth,
                trading_pairs=self._trading_pairs,
                api_factory=self._api_factory
            )
        return self._data_source

    @property
    def exchange_name(self) -> str:
        """
        *required
        Name of the current exchange
        """
        return EXCHANGE_NAME

    async def start(self):
        """
        *required
        Start all listeners and tasks
        """
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._ev_loop, self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
