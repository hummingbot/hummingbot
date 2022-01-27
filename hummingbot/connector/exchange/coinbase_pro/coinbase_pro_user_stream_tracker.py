#!/usr/bin/env python

import asyncio
import logging
from typing import List, Optional

from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_api_user_stream_data_source import (
    CoinbaseProAPIUserStreamDataSource
)
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger


class CoinbaseProUserStreamTracker(UserStreamTracker):
    _cbpust_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bust_logger is None:
            cls._bust_logger = logging.getLogger(__name__)
        return cls._bust_logger

    def __init__(
        self,
        trading_pairs: Optional[List[str]] = None,
        web_assistants_factory: Optional[WebAssistantsFactory] = None,
    ):
        super().__init__()
        self._trading_pairs: List[str] = trading_pairs or []
        self._web_assistants_factory = web_assistants_factory
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
            self._data_source = CoinbaseProAPIUserStreamDataSource(
                trading_pairs=self._trading_pairs,
                web_assistants_factory=self._web_assistants_factory,
            )
        return self._data_source

    @property
    def exchange_name(self) -> str:
        """
        *required
        Name of the current exchange
        """
        return "coinbase_pro"

    async def start(self):
        """
        *required
        Start all listeners and tasks
        """
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._ev_loop, self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
