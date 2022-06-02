import logging
from typing import (
    List,
    Optional,
)

from hummingbot.connector.exchange.okex.okex_api_user_stream_data_source import OkexAPIUserStreamDataSource
from hummingbot.connector.exchange.okex.okex_auth import OKExAuth
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.logger import HummingbotLogger


class OkexUserStreamTracker(UserStreamTracker):
    _okexust_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._okexust_logger is None:
            cls._okexust_logger = logging.getLogger(__name__)
        return cls._okexust_logger

    def __init__(self,
                 okex_auth: Optional[OKExAuth] = None,
                 trading_pairs: Optional[List[str]] = None,
                 ):
        self._okex_auth: OKExAuth = okex_auth
        self._trading_pairs: List[str] = trading_pairs or []
        super().__init__(data_source=OkexAPIUserStreamDataSource(
            okex_auth=self._okex_auth,
            trading_pairs=self._trading_pairs))

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        if not self._data_source:
            self._data_source = OkexAPIUserStreamDataSource(okex_auth=self._okex_auth, trading_pairs=self._trading_pairs)
        return self._data_source

    @property
    def exchange_name(self) -> str:
        return "okex"

    async def start(self):
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
