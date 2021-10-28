#!/usr/bin/env python

import asyncio
import logging

import aiohttp

import hummingbot.connector.exchange.probit.probit_constants as CONSTANTS

from typing import (
    Optional,
    List,
)

from hummingbot.connector.exchange.probit.probit_auth import ProbitAuth
from hummingbot.connector.exchange.probit.probit_api_user_stream_data_source import \
    ProbitAPIUserStreamDataSource
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.logger import HummingbotLogger


class ProbitUserStreamTracker(UserStreamTracker):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 probit_auth: Optional[ProbitAuth] = None,
                 trading_pairs: Optional[List[str]] = None,
                 domain: str = "com",
                 shared_client: Optional[aiohttp.ClientSession] = None):
        super().__init__()
        self._shared_client = shared_client
        self._domain: str = domain
        self._probit_auth: ProbitAuth = probit_auth
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
            self._data_source = ProbitAPIUserStreamDataSource(
                probit_auth=self._probit_auth,
                trading_pairs=self._trading_pairs,
                domain=self._domain,
                shared_client=self._shared_client,
            )
        return self._data_source

    @property
    def exchange_name(self) -> str:
        """
        *required
        Name of the current exchange
        """
        if self._domain == "com":
            return CONSTANTS.EXCHANGE_NAME
        else:
            return f"{CONSTANTS.EXCHANGE_NAME}_{self._domain}"

    async def start(self):
        """
        *required
        Start all listeners and tasks
        """
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._ev_loop, self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
