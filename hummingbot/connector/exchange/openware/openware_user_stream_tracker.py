#!/usr/bin/env python

# import asyncio
import logging
from typing import Optional, List

from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.connector.exchange.openware.openware_constants import Constants
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.connector.exchange.openware.openware_auth import OpenwareAuth

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

    def __init__(self,
                 throttler: Optional[AsyncThrottler] = None,
                 openware_auth: Optional[OpenwareAuth] = None,
                 trading_pairs: Optional[List[str]] = None):
        self._openware_auth: OpenwareAuth = openware_auth
        self._trading_pairs: List[str] = trading_pairs or []
        self._throttler = throttler or AsyncThrottler(Constants.RATE_LIMITS)
        super().__init__(data_source=OpenwareAPIUserStreamDataSource(
            openware_auth=self._openware_auth,
            trading_pairs=self._trading_pairs,
            throttler=self._throttler
        ))
        # self._data_source: Optional[UserStreamTrackerDataSource] = None
        # self._user_stream_tracking_task: Optional[asyncio.Task] = None

    @property
    def is_connected(self) -> float:
        return self._data_source.is_connected if self._data_source is not None else False

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        """
        *required
        Initializes a user stream data source (user specific order diffs from live socket stream)
        :return: OrderBookTrackerDataSource
        """
        if not self._data_source:
            self._data_source = OpenwareAPIUserStreamDataSource(
                throttler=self._throttler,
                openware_auth=self._openware_auth,
                trading_pairs=self._trading_pairs
            )
        return self._data_source

    @property
    def exchange_name(self) -> str:
        """
        *required
        Name of the current exchange
        """
        return Constants.EXCHANGE_NAME

    async def start(self):
        """
        *required
        Start all listeners and tasks
        """
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
