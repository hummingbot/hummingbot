#!/usr/bin/env python

from abc import (
    ABCMeta,
    abstractmethod
)
import asyncio
import pandas as pd
from typing import (
    Callable,
    Dict,
    List,
)

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry


class OrderBookTrackerDataSource(metaclass=ABCMeta):

    def __init__(self):
        self._order_book_create_function = lambda: OrderBook()

    @property
    def order_book_create_function(self) -> Callable[[], OrderBook]:
        return self._order_book_create_function

    @order_book_create_function.setter
    def order_book_create_function(self, func: Callable[[], OrderBook]):
        self._order_book_create_function = func

    @classmethod
    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    async def get_trading_pairs(self) -> List[str]:
        raise NotImplementedError

    @abstractmethod
    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        raise NotImplementedError

    @abstractmethod
    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Object type in the output queue must be OrderBookMessage
        """
        raise NotImplementedError

    @abstractmethod
    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Object type in the output queue must be OrderBookMessage
        """
        raise NotImplementedError

    @abstractmethod
    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Object type in the output queue must be OrderBookMessage
        """
        raise NotImplementedError
