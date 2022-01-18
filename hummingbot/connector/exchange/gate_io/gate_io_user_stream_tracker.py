#!/usr/bin/env python

import asyncio
import logging
from typing import List, Optional

from hummingbot.connector.exchange.gate_io import gate_io_constants as CONSTANTS
from hummingbot.connector.exchange.gate_io.gate_io_api_user_stream_data_source import GateIoAPIUserStreamDataSource
from hummingbot.connector.exchange.gate_io.gate_io_auth import GateIoAuth
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger


class GateIoUserStreamTracker(UserStreamTracker):
    _cbpust_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bust_logger is None:
            cls._bust_logger = logging.getLogger(__name__)
        return cls._bust_logger

    def __init__(self,
                 gate_io_auth: Optional[GateIoAuth] = None,
                 trading_pairs: Optional[List[str]] = None,
                 api_factory: Optional[WebAssistantsFactory] = None):
        super().__init__()
        self._api_factory = api_factory
        self._gate_io_auth: GateIoAuth = gate_io_auth
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
            self._data_source = GateIoAPIUserStreamDataSource(
                gate_io_auth=self._gate_io_auth,
                trading_pairs=self._trading_pairs,
                api_factory=self._api_factory,
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
