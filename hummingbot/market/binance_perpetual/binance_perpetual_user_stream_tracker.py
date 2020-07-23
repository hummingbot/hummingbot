import asyncio
import logging
from typing import Optional

from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker, UserStreamTrackerDataSourceType
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather, safe_ensure_future
from hummingbot.logger import HummingbotLogger

from hummingbot.market.binance_perpetual.binance_perpetual_user_stream_data_source import \
    BinancePerpetualUserStreamDataSource


class BinancePerpetualUserStreamTracker(UserStreamTracker):

    _bpust_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bust_logger is None:
            cls._bust_logger = logging.getLogger(__name__)
        return cls._bust_logger

    def __init__(self,
                 api_key: str,
                 data_source_type: UserStreamTrackerDataSourceType = UserStreamTrackerDataSourceType.EXCHANGE_API):
        super().__init__(data_source_type=data_source_type)
        self._api_key: str = api_key
        self._ev_loop: asyncio.events.AbstractEventLoop = asyncio.get_event_loop()
        self._data_source: Optional[UserStreamTrackerDataSource] = None
        self._user_stream_tracking_task: Optional[asyncio.Task] = None

    @property
    def exchange_name(self) -> str:
        return "binance_perpetuals"

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        if self._data_source is None:
            if self._data_source_type is UserStreamTrackerDataSourceType.EXCHANGE_API:
                self._data_source = BinancePerpetualUserStreamDataSource(api_key=self._api_key,
                                                                         )
            else:
                raise ValueError(f"data_source_type {self._data_source_type} is not supported.")
        return self._data_source

    async def start(self):
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._ev_loop, self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
