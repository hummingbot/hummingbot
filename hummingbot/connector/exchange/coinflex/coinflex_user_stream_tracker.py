import asyncio
import logging
from typing import Optional

import hummingbot.connector.exchange.coinflex.coinflex_constants as CONSTANTS
from hummingbot.connector.exchange.coinflex.coinflex_api_user_stream_data_source import CoinflexAPIUserStreamDataSource
from hummingbot.connector.exchange.coinflex.coinflex_auth import CoinflexAuth
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger


class CoinflexUserStreamTracker(UserStreamTracker):
    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: CoinflexAuth,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 throttler: Optional[AsyncThrottler] = None,
                 api_factory: Optional[WebAssistantsFactory] = None):
        super().__init__()
        self._auth: CoinflexAuth = auth
        self._ev_loop: asyncio.events.AbstractEventLoop = asyncio.get_event_loop()
        self._data_source: Optional[UserStreamTrackerDataSource] = None
        self._user_stream_tracking_task: Optional[asyncio.Task] = None
        self._domain = domain
        self._throttler = throttler
        self._api_factory = api_factory

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        """
        Returns the instance of the data source that listens to the private user channel to receive updates from the
        exchange. If the instance is not initialized it will be created.
        :return: the user stream instance that is listening to user updates from the server using the private channel
        """
        if not self._data_source:
            self._data_source = CoinflexAPIUserStreamDataSource(
                auth=self._auth,
                domain=self._domain,
                throttler=self._throttler,
                api_factory=self._api_factory
            )
        return self._data_source

    async def start(self):
        """
        Starts the background task that connects to the exchange and listens to user activity updates
        """
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._ev_loop, self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
