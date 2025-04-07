import logging
from typing import Optional

import aiohttp

from hummingbot.connector.exchange.ndax.ndax_api_user_stream_data_source import NdaxAPIUserStreamDataSource
from hummingbot.connector.exchange.ndax.ndax_auth import NdaxAuth
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.logger import HummingbotLogger


class NdaxUserStreamTracker(UserStreamTracker):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(
            self,
            throttler: AsyncThrottler,
            shared_client: Optional[aiohttp.ClientSession] = None,
            auth_assistant: Optional[NdaxAuth] = None,
            domain: Optional[str] = None
    ):
        self._auth_assistant: NdaxAuth = auth_assistant
        self._shared_client = shared_client
        self._domain = domain
        self._throttler = throttler
        super().__init__(data_source=NdaxAPIUserStreamDataSource(
            throttler=self._throttler,
            shared_client=self._shared_client,
            auth_assistant=self._auth_assistant,
            domain=self._domain
        ))

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        """
        Initializes a user stream data source (user specific order diffs from live socket stream)
        :return: UserStreamTrackerDataSource
        """
        if not self._data_source:
            self._data_source = NdaxAPIUserStreamDataSource(
                throttler=self._throttler, shared_client=self._shared_client, auth_assistant=self._auth_assistant,
                domain=self._domain
            )
        return self._data_source

    async def start(self):
        """
        Start all listeners and tasks
        """
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
