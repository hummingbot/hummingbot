import asyncio
import logging
from typing import Optional

from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather, safe_ensure_future
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

    def __init__(self, base_url: str, stream_url: str, api_key: str):
        super().__init__()
        self._api_key: str = api_key
        self._base_url = base_url
        self._stream_url = stream_url
        self._ev_loop: asyncio.events.AbstractEventLoop = asyncio.get_event_loop()
        self._data_source: Optional[UserStreamTrackerDataSource] = None
        self._user_stream_tracking_task: Optional[asyncio.Task] = None

    @property
    def exchange_name(self) -> str:
        return "binance_perpetuals"

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        if self._data_source is None:
            self._data_source = BinancePerpetualUserStreamDataSource(base_url=self._base_url, stream_url=self._stream_url, api_key=self._api_key)
        return self._data_source

    async def start(self):
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._ev_loop, self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
