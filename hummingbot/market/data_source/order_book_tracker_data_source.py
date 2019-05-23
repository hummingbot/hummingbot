#!/usr/bin/env python

from abc import (
    ABCMeta,
    abstractmethod
)
import asyncio
from typing import Dict
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry


class OrderBookTrackerDataSource(metaclass=ABCMeta):
    @abstractmethod
    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        raise NotImplementedError

    @abstractmethod
    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Object type in the output queue must be OrderBookRecord
        """
        raise NotImplementedError

    @abstractmethod
    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Object type in the output queue must be OrderBookRecord
        """
        raise NotImplementedError
