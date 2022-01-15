#!/usr/bin/env python

import asyncio
import logging
from typing import List, Optional

import aiohttp

from hummingbot.connector.exchange.btc_markets.btc_markets_api_user_stream_data_source import (
    BtcMarketsAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.btc_markets.btc_markets_auth import BtcMarketsAuth
from hummingbot.connector.exchange.btc_markets.btc_markets_constants import EXCHANGE_NAME
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger


class BtcMarketsUserStreamTracker(UserStreamTracker):
    _cbpust_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bust_logger is None:
            cls._bust_logger = logging.getLogger(__name__)
        return cls._bust_logger

    def __init__(self,
                 btc_markets_auth: Optional[BtcMarketsAuth] = None,
                 shared_client: Optional[aiohttp.ClientSession] = None,
                 trading_pairs: Optional[List[str]] = []):
        self._btc_markets_auth: BtcMarketsAuth = btc_markets_auth
        self._shared_client = shared_client or aiohttp.ClientSession()
        super().__init__(data_source=BtcMarketsAPIUserStreamDataSource(
            btc_markets_auth=self._btc_markets_auth
        ))
        self._btc_markets_auth: BtcMarketsAuth = btc_markets_auth
        self._trading_pairs: List[str] = trading_pairs
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
            self._data_source = BtcMarketsAPIUserStreamDataSource(
                btc_markets_auth=self._btc_markets_auth,
                trading_pairs=self._trading_pairs
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
