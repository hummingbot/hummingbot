#!/usr/bin/env python

# import asyncio
import logging
from typing import Optional

from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker

from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)

from hummingbot.connector.exchange.openware.openware_api_user_stream_data_source import OpenwareAPIUserStreamDataSource
# from hummingbot.connector.exchange.openware.lib.client import Client as OpenwareClient


class OpenwareUserStreamTracker(UserStreamTracker):
    _bust_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bust_logger is None:
            cls._bust_logger = logging.getLogger(__name__)
        return cls._bust_logger

    def __init__(self):
        super().__init__(data_source=OpenwareAPIUserStreamDataSource())
        # self._data_source: Optional[UserStreamTrackerDataSource] = None
        # self._user_stream_tracking_task: Optional[asyncio.Task] = None

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        if not self._data_source:
            self._data_source = OpenwareAPIUserStreamDataSource()
        return self._data_source

    @property
    def exchange_name(self) -> str:
        return "openware"

    async def start(self):
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
