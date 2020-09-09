#!/usr/bin/env python

import asyncio
from abc import abstractmethod, ABC
from enum import Enum
import logging
from typing import (
    Optional
)
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger


class UserStreamTrackerDataSourceType(Enum):
    # LOCAL_CLUSTER = 1 deprecated
    REMOTE_API = 2
    EXCHANGE_API = 3


class UserStreamTracker(ABC):
    _ust_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._ust_logger is None:
            cls._ust_logger = logging.getLogger(__name__)
        return cls._ust_logger

    def __init__(self):
        self._user_stream: asyncio.Queue = asyncio.Queue()
        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()

    @property
    @abstractmethod
    def data_source(self) -> UserStreamTrackerDataSource:
        raise NotImplementedError

    @property
    def last_recv_time(self) -> float:
        return self.data_source.last_recv_time

    @abstractmethod
    async def start(self):
        raise NotImplementedError

    @property
    def user_stream(self) -> asyncio.Queue:
        return self._user_stream
