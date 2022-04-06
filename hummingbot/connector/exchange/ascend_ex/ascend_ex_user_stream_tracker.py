import logging
from typing import List, Optional

from hummingbot.connector.exchange.ascend_ex import ascend_ex_constants as CONSTANTS
from hummingbot.connector.exchange.ascend_ex.ascend_ex_api_user_stream_data_source import (
    AscendExAPIUserStreamDataSource
)
from hummingbot.connector.exchange.ascend_ex.ascend_ex_auth import AscendExAuth
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger


class AscendExUserStreamTracker(UserStreamTracker):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 api_factory: Optional[WebAssistantsFactory] = None,
                 throttler: Optional[AsyncThrottler] = None,
                 ascend_ex_auth: Optional[AscendExAuth] = None,
                 trading_pairs: Optional[List[str]] = None):
        self._api_factory = api_factory
        self._throttler = throttler
        self._ascend_ex_auth: AscendExAuth = ascend_ex_auth
        self._trading_pairs: List[str] = trading_pairs or []
        super().__init__(data_source=AscendExAPIUserStreamDataSource(
            api_factory=self._api_factory,
            throttler=self._throttler,
            ascend_ex_auth=self._ascend_ex_auth,
            trading_pairs=self._trading_pairs
        ))

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        """
        Returns the instance of the data source that listens to the private user channel to receive updates from the
        exchange. If the instance is not initialized it will be created.
        :return: the user stream instance that is listening to user updates from the server using the private channel
        """
        if not self._data_source:
            self._data_source = AscendExAPIUserStreamDataSource(
                api_factory=self._api_factory,
                throttler=self._throttler,
                ascend_ex_auth=self._ascend_ex_auth,
                trading_pairs=self._trading_pairs
            )
        return self._data_source

    @property
    def exchange_name(self) -> str:
        """
        Name of the current exchange
        """
        return CONSTANTS.EXCHANGE_NAME

    async def start(self):
        """
        Starts the background task that connects to the exchange and listens to user activity updates
        """
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
