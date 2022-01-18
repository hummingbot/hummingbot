#!/usr/bin/env python

import asyncio
import logging

from typing import Optional

from hummingbot.connector.exchange.huobi.huobi_api_user_stream_data_source import HuobiAPIUserStreamDataSource
from hummingbot.connector.exchange.huobi.huobi_auth import HuobiAuth
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger


class HuobiUserStreamTracker(UserStreamTracker):
    _hust_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._hust_logger is None:
            cls._hust_logger = logging.getLogger(__name__)
        return cls._hust_logger

    def __init__(
        self,
        huobi_auth: Optional[HuobiAuth] = None,
        api_factory: Optional[WebAssistantsFactory] = None,
    ):
        super().__init__()
        self._huobi_auth: HuobiAuth = huobi_auth
        self._ev_loop: asyncio.events.AbstractEventLoop = asyncio.get_event_loop()
        self._data_source: Optional[UserStreamTrackerDataSource] = None
        self._user_stream_tracking_task: Optional[asyncio.Task] = None
        self._api_factory = api_factory

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        if not self._data_source:
            self._data_source = HuobiAPIUserStreamDataSource(huobi_auth=self._huobi_auth,
                                                             api_factory=self._api_factory)
        return self._data_source

    @property
    def exchange_name(self) -> str:
        return "huobi"

    async def start(self):
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._ev_loop, self._user_stream)
        )
        await asyncio.gather(self._user_stream_tracking_task)
