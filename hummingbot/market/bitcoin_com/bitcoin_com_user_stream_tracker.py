#!/usr/bin/env python

import asyncio
import logging
import hummingbot.market.bitcoin_com.bitcoin_com_constants as constants

from typing import Optional, List
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.user_stream_tracker import UserStreamTrackerDataSourceType, UserStreamTracker
from hummingbot.market.bitcoin_com.bitcoin_com_api_user_stream_data_source import BitcoinComAPIUserStreamDataSource
from hummingbot.market.bitcoin_com.bitcoin_com_auth import BitcoinComAuth


class BitcoinComUserStreamTracker(UserStreamTracker):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(
        self,
        data_source_type: UserStreamTrackerDataSourceType = UserStreamTrackerDataSourceType.EXCHANGE_API,
        bitcoin_com_auth: Optional[BitcoinComAuth] = None,
        trading_pairs: Optional[List[str]] = [],
    ):
        super().__init__(data_source_type=data_source_type)
        self._bitcoin_com_auth: BitcoinComAuth = bitcoin_com_auth
        self._trading_pairs: List[str] = trading_pairs
        self._ev_loop: asyncio.events.AbstractEventLoop = asyncio.get_event_loop()
        self._data_source: Optional[UserStreamTrackerDataSource] = None
        self._user_stream_tracking_task: Optional[asyncio.Task] = None

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        if not self._data_source:
            if self._data_source_type is UserStreamTrackerDataSourceType.EXCHANGE_API:
                self._data_source = BitcoinComAPIUserStreamDataSource(
                    bitcoin_com_auth=self._bitcoin_com_auth, trading_pairs=self._trading_pairs
                )
            else:
                raise ValueError(f"data_source_type {self._data_source_type} is not supported.")
        return self._data_source

    @property
    def exchange_name(self) -> str:
        return constants.EXCHANGE_NAME

    async def start(self):
        self._user_stream_tracking_task = asyncio.ensure_future(
            self.data_source.listen_for_user_stream(self._ev_loop, self._user_stream)
        )
        await asyncio.gather(self._user_stream_tracking_task)
