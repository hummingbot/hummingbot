#!/usr/bin/env python

import asyncio
import logging

from typing import (
    Optional
)

from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_user_stream_data_source import DydxPerpetualUserStreamDataSource
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_auth import DydxPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger


class DydxPerpetualUserStreamTracker(UserStreamTracker):
    _krust_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._krust_logger is None:
            cls._krust_logger = logging.getLogger(__name__)
        return cls._krust_logger

    def __init__(self, dydx_auth: DydxPerpetualAuth, api_factory: Optional[WebAssistantsFactory] = None):
        super().__init__()
        self._ev_loop: asyncio.events.AbstractEventLoop = asyncio.get_event_loop()
        self._data_source: Optional[UserStreamTrackerDataSource] = None
        self._user_stream_tracking_task: Optional[asyncio.Task] = None
        self._dydx_auth: DydxPerpetualAuth = dydx_auth
        self._api_factory = api_factory

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        if not self._data_source:
            self._data_source = DydxPerpetualUserStreamDataSource(dydx_auth=self._dydx_auth,
                                                                  api_factory=self._api_factory)
        return self._data_source

    @property
    def exchange_name(self) -> str:
        return "dydx_perpetual"

    async def start(self):
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._ev_loop, self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
