import asyncio
import logging
import aiohttp
from typing import Optional

from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather, safe_ensure_future
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.derivative.bybit_perpetual import bybit_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_auth import BybitPerpetualAuth

from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_user_stream_data_source import BybitPerpetualUserStreamDataSource


class BybitPerpetualUserStreamTracker(UserStreamTracker):

    _bpust_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bust_logger is None:
            cls._bust_logger = logging.getLogger(__name__)
        return cls._bust_logger

    def __init__(self, auth_assistant: BybitPerpetualAuth, domain: Optional[str] = None, session: Optional[aiohttp.ClientSession] = None):
        super().__init__()
        self._data_source: Optional[UserStreamTrackerDataSource] = None
        self._user_stream_tracking_task: Optional[asyncio.Task] = None

        self._auth_assistant = auth_assistant
        self._domain = domain
        self._session = session

        if self._session is None:
            self._session = aiohttp.ClientSession()

    @property
    def exchange_name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        if self._data_source is None:
            self._data_source = BybitPerpetualUserStreamDataSource(auth_assistant=self._auth_assistant, session=self._session, domain=self._domain)
        return self._data_source

    async def start(self):
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
