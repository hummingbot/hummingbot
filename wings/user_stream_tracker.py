#!/usr/bin/env python
import asyncio
from abc import abstractmethod, ABC
from enum import Enum
import logging
from typing import (
    Optional
)
from hummingbot.market.data_source.user_stream_tracker_data_source import UserStreamTrackerDataSource


class UserStreamTrackerDataSourceType(Enum):
    LOCAL_CLUSTER = 1
    REMOTE_API = 2
    EXCHANGE_API = 3


class UserStreamTracker(ABC):
    _ust_logger: Optional[logging.Logger] = None

    @classmethod
    def logger(cls) -> logging.Logger:
        if cls._ust_logger is None:
            cls._ust_logger = logging.getLogger(__name__)
        return cls._ust_logger

    def __init__(self,
                 data_source_type: UserStreamTrackerDataSourceType = UserStreamTrackerDataSourceType.EXCHANGE_API):
        self._data_source_type: UserStreamTrackerDataSourceType = data_source_type
        self._user_stream: asyncio.Queue = asyncio.Queue()
        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()

    @property
    @abstractmethod
    def data_source(self) -> UserStreamTrackerDataSource:
        raise NotImplementedError

    @abstractmethod
    async def start(self):
        raise NotImplementedError

    @property
    def user_stream(self) -> asyncio.Queue:
        return self._user_stream
