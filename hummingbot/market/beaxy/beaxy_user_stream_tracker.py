#!/usr/bin/env python

import asyncio
from logging import Logger
from hummingbot.market.beaxy.beaxy_auth import BeaxyAuth
import logging
from typing import (
    Optional
)
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.data_type.user_stream_tracker import (
    UserStreamTrackerDataSourceType,
    UserStreamTracker
)
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.market.beaxy.beaxy_api_user_stream_data_source import BeaxyAPIUserStreamDataSource


class BeaxyUserStreamTracker(UserStreamTracker):
    _bxyust_logger: Optional[Logger] = None

    @classmethod
    def logger(cls) -> Logger:
        if cls._bxyust_logger is None:
            cls._bxyust_logger = logging.getLogger(__name__)
        return cls._bxyust_logger

    def __init__(self,
                 beaxy_auth: BeaxyAuth,
                 data_source_type: UserStreamTrackerDataSourceType = UserStreamTrackerDataSourceType.EXCHANGE_API):
        super().__init__(data_source_type=data_source_type)
        self._beaxy_auth = beaxy_auth
        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._data_source: Optional[UserStreamTrackerDataSource] = None
        self._user_stream_tracking_task = None

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        if not self._data_source:
            if self._data_source_type is UserStreamTrackerDataSourceType.EXCHANGE_API:
                self._data_source = BeaxyAPIUserStreamDataSource(beaxy_auth=self._beaxy_auth)
            else:
                raise ValueError(f"data_source_type {self._data_source_type} is not supported.")
        return self._data_source

    @property
    def exchange_name(self) -> str:
        return "beaxy"

    async def start(self):
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._ev_loop, self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
