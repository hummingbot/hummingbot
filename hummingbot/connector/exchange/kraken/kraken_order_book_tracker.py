#!/usr/bin/env python

import asyncio
from collections import deque, defaultdict
import logging
import time
from typing import (
    Deque,
    Dict,
    List,
    Optional
)

from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_tracker import (
    OrderBookTracker
)
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.connector.exchange.kraken.kraken_api_order_book_data_source import KrakenAPIOrderBookDataSource
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.utils.async_utils import wait_til


class KrakenOrderBookTracker(OrderBookTracker):
    _krobt_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._krobt_logger is None:
            cls._krobt_logger = logging.getLogger(__name__)
        return cls._krobt_logger

    def __init__(self, trading_pairs: List[str]):
        super().__init__(KrakenAPIOrderBookDataSource(trading_pairs), trading_pairs)
        self._order_book_diff_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()
        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._saved_message_queues: Dict[str, Deque[OrderBookMessage]] = defaultdict(lambda: deque(maxlen=1000))

    @property
    def data_source(self) -> OrderBookTrackerDataSource:
        if not self._data_source:
            self._data_source = KrakenAPIOrderBookDataSource(trading_pairs=self._trading_pairs)
        return self._data_source

    @property
    def exchange_name(self) -> str:
        return "kraken"

    async def _order_book_diff_router(self):
        """
        Route the real-time order book diff messages to the correct order book.
        """
        last_message_timestamp: float = time.time()
        messages_accepted: int = 0
        messages_rejected: int = 0

        await wait_til(lambda: len(self.data_source._trading_pairs) == len(self._order_books.keys()))
        while True:
            try:
                ob_message: OrderBookMessage = await self._order_book_diff_stream.get()
                trading_pair: str = ob_message.trading_pair

                if trading_pair not in self._tracking_message_queues:
                    messages_rejected += 1
                    continue
                message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
                # Check the order book's initial update ID. If it's larger, don't bother.
                order_book: OrderBook = self._order_books[trading_pair]

                if order_book.snapshot_uid > ob_message.update_id:
                    messages_rejected += 1
                    continue
                await message_queue.put(ob_message)
                messages_accepted += 1

                # Log some statistics.
                now: float = time.time()
                if int(now / 60.0) > int(last_message_timestamp / 60.0):
                    self.logger().debug(f"Diff messages processed: {messages_accepted}, rejected: {messages_rejected}")
                    messages_accepted = 0
                    messages_rejected = 0

                last_message_timestamp = now
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unknown error. Retrying after 5 seconds.", exc_info=True)
                await asyncio.sleep(5.0)
