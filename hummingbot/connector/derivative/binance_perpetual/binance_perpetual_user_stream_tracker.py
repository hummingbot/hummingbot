import asyncio
import logging
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_auth import BinancePerpetualAuth

import hummingbot.connector.derivative.binance_perpetual.constants as CONSTANTS

from typing import Optional

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather, safe_ensure_future
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger

from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_user_stream_data_source import \
    BinancePerpetualUserStreamDataSource


class BinancePerpetualUserStreamTracker(UserStreamTracker):

    _bpust_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bust_logger is None:
            cls._bust_logger = logging.getLogger(__name__)
        return cls._bust_logger

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        return AsyncThrottler(CONSTANTS.RATE_LIMITS)

    def __init__(self,
                 auth: BinancePerpetualAuth,
                 domain: str = CONSTANTS.DOMAIN,
                 throttler: Optional[AsyncThrottler] = None,
                 api_factory: Optional[WebAssistantsFactory] = None):
        super().__init__()
        self._auth: BinancePerpetualAuth = auth
        self._ev_loop: asyncio.events.AbstractEventLoop = asyncio.get_event_loop()
        self._data_source: Optional[UserStreamTrackerDataSource] = None
        self._user_stream_tracking_task: Optional[asyncio.Task] = None
        self._domain = domain
        self._throttler = throttler
        self._api_factory = api_factory

    @property
    def exchange_name(self) -> str:
        return self._domain

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        if self._data_source is None:
            self._data_source = BinancePerpetualUserStreamDataSource(
                auth=self._auth,
                domain=self._domain,
                throttler=self._throttler,
                api_factory=self._api_factory)
        return self._data_source

    async def start(self):
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._ev_loop, self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
