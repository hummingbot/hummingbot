#!/usr/bin/env python

import asyncio
import bisect
import logging
import time
from collections import deque, defaultdict
from typing import (
    Optional,
    Deque,
    List,
    Dict,
    Set,
)
from hummingbot.market.ddex.ddex_active_order_tracker import DDEXActiveOrderTracker
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_tracker import (
    OrderBookTracker,
    OrderBookTrackerDataSourceType
)
from hummingbot.market.ddex.ddex_order_book import DDEXOrderBook
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.remote_api_order_book_data_source import RemoteAPIOrderBookDataSource
from hummingbot.market.ddex.ddex_api_order_book_data_source import DDEXAPIOrderBookDataSource

from hummingbot.core.data_type.order_book_message import (
    OrderBookMessageType,
    DDEXOrderBookMessage
)
from hummingbot.core.data_type.order_book_tracker_entry import DDEXOrderBookTrackerEntry


class DDEXOrderBookTracker(OrderBookTracker):
    _dobt_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._dobt_logger is None:
            cls._dobt_logger = logging.getLogger(__name__)
        return cls._dobt_logger

    def __init__(self,
                 data_source_type: OrderBookTrackerDataSourceType = OrderBookTrackerDataSourceType.EXCHANGE_API,
                 symbols: Optional[List[str]] = None):
        super().__init__(data_source_type=data_source_type)
        self._past_diffs_windows: Dict[str, Deque] = {}
        self._order_books: Dict[str, DDEXOrderBook] = {}
        self._saved_message_queues: Dict[str, Deque[DDEXOrderBookMessage]] = defaultdict(lambda: deque(maxlen=1000))
        self._order_book_diff_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()
        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._data_source: Optional[OrderBookTrackerDataSource] = None
        self._active_order_trackers: Dict[str, DDEXActiveOrderTracker] = defaultdict(DDEXActiveOrderTracker)
        self._symbols: Optional[List[str]] = symbols

    @property
    def data_source(self) -> OrderBookTrackerDataSource:
        if not self._data_source:
            if self._data_source_type is OrderBookTrackerDataSourceType.REMOTE_API:
                self._data_source = RemoteAPIOrderBookDataSource()
            elif self._data_source_type is OrderBookTrackerDataSourceType.EXCHANGE_API:
                self._data_source = DDEXAPIOrderBookDataSource(symbols=self._symbols)
            else:
                raise ValueError(f"data_source_type {self._data_source_type} is not supported.")
        return self._data_source

    @property
    async def exchange_name(self) -> str:
        return "ddex"

    async def start(self):
        self._order_book_diff_listener_task = asyncio.ensure_future(
            self.data_source.listen_for_order_book_diffs(self._ev_loop, self._order_book_diff_stream)
        )
        self._order_book_snapshot_listener_task = asyncio.ensure_future(
            self.data_source.listen_for_order_book_snapshots(self._ev_loop, self._order_book_snapshot_stream)
        )
        self._refresh_tracking_task = asyncio.ensure_future(
            self._refresh_tracking_loop()
        )
        self._order_book_diff_router_task = asyncio.ensure_future(
            self._order_book_diff_router()
        )
        self._order_book_snapshot_router_task = asyncio.ensure_future(
            self._order_book_snapshot_router()
        )

        await asyncio.gather(self._order_book_snapshot_listener_task,
                             self._order_book_diff_listener_task,
                             self._order_book_snapshot_router_task,
                             self._order_book_diff_router_task,
                             self._refresh_tracking_task)

    async def _refresh_tracking_tasks(self):
        """
        Starts tracking for any new trading pairs, and stop tracking for any inactive trading pairs.
        """
        tracking_symbols: Set[str] = set([key for key in self._tracking_tasks.keys()
                                          if not self._tracking_tasks[key].done()])
        available_pairs: Dict[str, DDEXOrderBookTrackerEntry] = await self.data_source.get_tracking_pairs()
        available_symbols: Set[str] = set(available_pairs.keys())
        new_symbols: Set[str] = available_symbols - tracking_symbols
        deleted_symbols: Set[str] = tracking_symbols - available_symbols

        for symbol in new_symbols:
            order_book_tracker_entry: DDEXOrderBookTrackerEntry = available_pairs[symbol]
            self._active_order_trackers[symbol] = order_book_tracker_entry.active_order_tracker
            self._order_books[symbol] = order_book_tracker_entry.order_book
            self._tracking_message_queues[symbol] = asyncio.Queue()
            self._tracking_tasks[symbol] = asyncio.ensure_future(self._track_single_book(symbol))
            self.logger().info("Started order book tracking for %s.", symbol)

        for symbol in deleted_symbols:
            self._tracking_tasks[symbol].cancel()
            del self._tracking_tasks[symbol]
            del self._order_books[symbol]
            del self._active_order_trackers[symbol]
            del self._tracking_message_queues[symbol]
            self.logger().info("Stopped order book tracking for %s.", symbol)

    async def _order_book_diff_router(self):
        """
        Route the real-time order book diff messages to the correct order book.
        """
        last_message_timestamp: float = time.time()
        messages_queued: int = 0
        messages_accepted: int = 0
        messages_rejected: int = 0

        while True:
            try:
                ob_message: DDEXOrderBookMessage = await self._order_book_diff_stream.get()
                symbol: str = ob_message.symbol

                if symbol not in self._tracking_message_queues:
                    messages_queued += 1
                    # Save diff messages received before snapshots are ready
                    self._saved_message_queues[symbol].append(ob_message)
                    continue
                message_queue: asyncio.Queue = self._tracking_message_queues[symbol]
                # Check the order book's initial update ID. If it's larger, don't bother.
                order_book: DDEXOrderBook = self._order_books[symbol]

                if order_book.snapshot_uid > ob_message.update_id:
                    messages_rejected += 1
                    continue
                await message_queue.put(ob_message)
                messages_accepted += 1

                # Log some statistics.
                now: float = time.time()
                if int(now / 60.0) > int(last_message_timestamp / 60.0):
                    self.logger().info("Diff messages processed: %d, rejected: %d, queued: %d",
                                       messages_accepted,
                                       messages_rejected,
                                       messages_queued)
                    messages_accepted = 0
                    messages_rejected = 0
                    messages_queued = 0

                last_message_timestamp = now
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unknown error. Retrying after 5 seconds.", exc_info=True)
                await asyncio.sleep(5.0)

    async def _track_single_book(self, symbol: str):
        past_diffs_window: Deque[DDEXOrderBookMessage] = deque()
        self._past_diffs_windows[symbol] = past_diffs_window

        message_queue: asyncio.Queue = self._tracking_message_queues[symbol]
        order_book: DDEXOrderBook = self._order_books[symbol]
        active_order_tracker: DDEXActiveOrderTracker = self._active_order_trackers[symbol]

        last_message_timestamp: float = time.time()
        diff_messages_accepted: int = 0

        while True:
            try:
                message: DDEXOrderBookMessage = None
                saved_messages: Deque[DDEXOrderBookMessage] = self._saved_message_queues[symbol]
                # Process saved messages first if there are any
                if len(saved_messages) > 0:
                    message = saved_messages.popleft()
                else:
                    message = await message_queue.get()

                if message.type is OrderBookMessageType.DIFF:
                    bids, asks = active_order_tracker.convert_diff_message_to_order_book_row(message)
                    order_book.apply_diffs(bids, asks, message.update_id)
                    past_diffs_window.append(message)
                    while len(past_diffs_window) > self.PAST_DIFF_WINDOW_SIZE:
                        past_diffs_window.popleft()
                    diff_messages_accepted += 1

                    # Output some statistics periodically.
                    now: float = time.time()
                    if int(now / 60.0) > int(last_message_timestamp / 60.0):
                        self.logger().info("Processed %d order book diffs for %s.",
                                           diff_messages_accepted, symbol)
                        diff_messages_accepted = 0
                    last_message_timestamp = now
                elif message.type is OrderBookMessageType.SNAPSHOT:
                    past_diffs: List[DDEXOrderBookMessage] = list(past_diffs_window)
                    # only replay diffs later than snapshot, first update active order with snapshot then replay diffs
                    replay_position = bisect.bisect_right(past_diffs, message)
                    replay_diffs = past_diffs[replay_position:]
                    s_bids, s_asks = active_order_tracker.convert_snapshot_message_to_order_book_row(message)
                    order_book.apply_snapshot(s_bids, s_asks, message.update_id)
                    for diff_message in replay_diffs:
                        d_bids, d_asks = active_order_tracker.convert_diff_message_to_order_book_row(diff_message)
                        order_book.apply_diffs(d_bids, d_asks, diff_message.update_id)

                    self.logger().debug("Processed order book snapshot for %s.", symbol)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unknown error. Retrying after 5 seconds.", exc_info=True)
                await asyncio.sleep(5.0)
