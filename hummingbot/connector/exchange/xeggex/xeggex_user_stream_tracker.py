import logging
from typing import List, Optional

from hummingbot.connector.exchange.xeggex.xeggex_api_user_stream_data_source import XeggexAPIUserStreamDataSource
from hummingbot.connector.exchange.xeggex.xeggex_auth import XeggexAuth
from hummingbot.connector.exchange.xeggex.xeggex_constants import Constants
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger


class XeggexUserStreamTracker(UserStreamTracker):
    _cbpust_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bust_logger is None:
            cls._bust_logger = logging.getLogger(__name__)
        return cls._bust_logger

    def __init__(self,
                 xeggex_auth: Optional[XeggexAuth] = None,
                 trading_pairs: Optional[List[str]] = None):
        self._xeggex_auth: XeggexAuth = xeggex_auth
        self._trading_pairs: List[str] = trading_pairs or []
        super().__init__(data_source=XeggexAPIUserStreamDataSource(
            xeggex_auth=self._xeggex_auth,
            trading_pairs=self._trading_pairs
        ))

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        """
        *required
        Initializes a user stream data source (user specific order diffs from live socket stream)
        :return: OrderBookTrackerDataSource
        """
        if not self._data_source:
            self._data_source = XeggexAPIUserStreamDataSource(
                xeggex_auth=self._xeggex_auth,
                trading_pairs=self._trading_pairs
            )
        return self._data_source

    @property
    def exchange_name(self) -> str:
        """
        *required
        Name of the current exchange
        """
        return Constants.EXCHANGE_NAME

    async def start(self):
        """
        *required
        Start all listeners and tasks
        """
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
