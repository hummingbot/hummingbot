#!/usr/bin/env python
import logging
from typing import TYPE_CHECKING, List, Optional

from hummingbot.connector.exchange.southxchange.southxchange_api_user_stream_data_source import (
    SouthxchangeAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.southxchange.southxchange_auth import SouthXchangeAuth
from hummingbot.connector.exchange.southxchange.southxchange_constants import EXCHANGE_NAME
from hummingbot.connector.exchange.southxchange.southxchange_web_utils import WebAssistantsFactory_SX
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.southxchange.southxchange_exchange import SouthxchangeExchange


class SouthxchangeUserStreamTracker(UserStreamTracker):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(
            self,
            connector: 'SouthxchangeExchange',
            api_factory: Optional[WebAssistantsFactory_SX] = None,
            throttler: Optional[AsyncThrottler] = None,
            southxchange_auth: Optional[SouthXchangeAuth] = None,
            trading_pairs: Optional[List[str]] = None,
    ):
        self._api_factory = api_factory
        self._throttler = throttler
        self._southxchange_auth: SouthXchangeAuth = southxchange_auth
        self._trading_pairs: List[str] = trading_pairs or []
        self._connector = connector
        super().__init__(data_source=SouthxchangeAPIUserStreamDataSource(
            connector=self._connector,
            api_factory=self._api_factory,
            throttler=self._throttler,
            southxchange_auth=self._southxchange_auth,
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
            self._data_source = SouthxchangeAPIUserStreamDataSource(
                api_factory=self._api_factory,
                throttler=self._throttler,
                southxchange_auth=self._southxchange_auth,
                trading_pairs=self._trading_pairs,
                connector=self._connector
            )
        return self._data_source

    @property
    def exchange_name(self) -> str:
        """
        *required
        Name of the current exchange
        """
        return EXCHANGE_NAME

    async def start(self):
        """
        *required
        Start all listeners and tasks
        """
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
