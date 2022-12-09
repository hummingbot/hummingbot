import logging
from typing import (
    List,
    Optional,
)

import aiohttp

from hummingbot.connector.exchange.mexc.mexc_api_user_stream_data_source import MexcAPIUserStreamDataSource
from hummingbot.connector.exchange.mexc.mexc_auth import MexcAuth
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.logger import HummingbotLogger


class MexcUserStreamTracker(UserStreamTracker):
    _mexcust_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._mexcust_logger is None:
            cls._mexcust_logger = logging.getLogger(__name__)
        return cls._mexcust_logger

    def __init__(self,
                 throttler: AsyncThrottler,
                 mexc_auth: Optional[MexcAuth] = None,
                 trading_pairs: Optional[List[str]] = None,
                 shared_client: Optional[aiohttp.ClientSession] = None
                 ):
        self._shared_client = shared_client
        self._mexc_auth: MexcAuth = mexc_auth
        self._trading_pairs: List[str] = trading_pairs or []
        self._throttler = throttler
        super().__init__(data_source=MexcAPIUserStreamDataSource(
            throttler=self._throttler,
            mexc_auth=self._mexc_auth,
            trading_pairs=self._trading_pairs,
            shared_client=self._shared_client))

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        if not self._data_source:
            self._data_source = MexcAPIUserStreamDataSource(throttler=self._throttler,
                                                            mexc_auth=self._mexc_auth,
                                                            trading_pairs=self._trading_pairs,
                                                            shared_client=self._shared_client)
        return self._data_source

    @property
    def exchange_name(self) -> str:
        return "mexc"

    async def start(self):
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
