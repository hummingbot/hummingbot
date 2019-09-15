#!/usr/bin/env python

import asyncio
import bisect
<<<<<<< HEAD
from collections import defaultdict, deque
import logging
import time
from typing import Deque, Dict, List, Optional, Set
=======
from collections import (
    defaultdict,
    deque
)
import logging
import time
from typing import (
    Deque,
    Dict,
    List,
    Optional,
    Set
)
>>>>>>> Created bitroyal connector folder and files in hummingbot>market

from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker, OrderBookTrackerDataSourceType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
<<<<<<< HEAD
from hummingbot.market.bitroyal.bitroyal_api_order_book_data_source import bitroyalAPIOrderBookDataSource
from hummingbot.core.data_type.order_book_message import OrderBookMessageType, bitroyalOrderBookMessage
from hummingbot.core.data_type.order_book_tracker_entry import bitroyalOrderBookTrackerEntry
from hummingbot.market.bitroyal.bitroyal_order_book import bitroyalOrderBook
from hummingbot.market.bitroyal.bitroyal_active_order_tracker import bitroyalActiveOrderTracker


class bitroyalOrderBookTracker(OrderBookTracker):
=======
from hummingbot.market.coinbase_pro.coinbase_pro_api_order_book_data_source import CoinbaseProAPIOrderBookDataSource
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessageType,
    CoinbaseProOrderBookMessage
)
from hummingbot.core.data_type.order_book_tracker_entry import CoinbaseProOrderBookTrackerEntry
from hummingbot.market.coinbase_pro.coinbase_pro_order_book import CoinbaseProOrderBook
from hummingbot.market.coinbase_pro.coinbase_pro_active_order_tracker import CoinbaseProActiveOrderTracker


class CoinbaseProOrderBookTracker(OrderBookTracker):
>>>>>>> Created bitroyal connector folder and files in hummingbot>market
    _cbpobt_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._cbpobt_logger is None:
            cls._cbpobt_logger = logging.getLogger(__name__)
        return cls._cbpobt_logger

<<<<<<< HEAD
    def __init__(
        self,
        data_source_type: OrderBookTrackerDataSourceType = OrderBookTrackerDataSourceType.EXCHANGE_API,
        symbols: Optional[List[str]] = None,
    ):
=======
    def __init__(self,
                 data_source_type: OrderBookTrackerDataSourceType = OrderBookTrackerDataSourceType.EXCHANGE_API,
                 symbols: Optional[List[str]] = None):
>>>>>>> Created bitroyal connector folder and files in hummingbot>market
        super().__init__(data_source_type=data_source_type)

        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._data_source: Optional[OrderBookTrackerDataSource] = None
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_diff_stream: asyncio.Queue = asyncio.Queue()
        self._process_msg_deque_task: Optional[asyncio.Task] = None
        self._past_diffs_windows: Dict[str, Deque] = {}
<<<<<<< HEAD
        self._order_books: Dict[str, bitroyalOrderBook] = {}
        self._saved_message_queues: Dict[str, Deque[bitroyalOrderBookMessage]] = defaultdict(lambda: deque(maxlen=1000))
        self._active_order_trackers: Dict[str, bitroyalActiveOrderTracker] = defaultdict(bitroyalActiveOrderTracker)
=======
        self._order_books: Dict[str, CoinbaseProOrderBook] = {}
        self._saved_message_queues: Dict[str, Deque[CoinbaseProOrderBookMessage]] = defaultdict(lambda: deque(maxlen=1000))
        self._active_order_trackers: Dict[str, CoinbaseProActiveOrderTracker] = defaultdict(CoinbaseProActiveOrderTracker)
>>>>>>> Created bitroyal connector folder and files in hummingbot>market
        self._symbols: Optional[List[str]] = symbols

    @property
    def data_source(self) -> OrderBookTrackerDataSource:
        if not self._data_source:
            if self._data_source_type is OrderBookTrackerDataSourceType.EXCHANGE_API:
<<<<<<< HEAD
                self._data_source = bitroyalAPIOrderBookDataSource(symbols=self._symbols)
=======
                self._data_source = CoinbaseProAPIOrderBookDataSource(symbols=self._symbols)
>>>>>>> Created bitroyal connector folder and files in hummingbot>market
            else:
                raise ValueError(f"data_source_type {self._data_source_type} is not supported.")
        return self._data_source

    @property
    async def exchange_name(self) -> str:
<<<<<<< HEAD
        return "bitroyal"
=======
        return "coinbase_pro"
>>>>>>> Created bitroyal connector folder and files in hummingbot>market

    async def start(self):
        self._order_book_diff_listener_task = asyncio.ensure_future(
            self.data_source.listen_for_order_book_diffs(self._ev_loop, self._order_book_diff_stream)
        )
        self._order_book_snapshot_listener_task = asyncio.ensure_future(
            self.data_source.listen_for_order_book_snapshots(self._ev_loop, self._order_book_snapshot_stream)
        )
<<<<<<< HEAD
        self._refresh_tracking_task = asyncio.ensure_future(self._refresh_tracking_loop())
        self._order_book_diff_router_task = asyncio.ensure_future(self._order_book_diff_router())
        self._order_book_snapshot_router_task = asyncio.ensure_future(self._order_book_snapshot_router())

        await asyncio.gather(
            self._order_book_snapshot_listener_task,
            self._order_book_diff_listener_task,
            self._order_book_snapshot_router_task,
            self._order_book_diff_router_task,
            self._refresh_tracking_task,
        )

=======
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

>>>>>>> Created bitroyal connector folder and files in hummingbot>market
    async def _refresh_tracking_tasks(self):
        """
        Starts tracking for any new trading pairs, and stop tracking for any inactive trading pairs.
        """
<<<<<<< HEAD
        tracking_symbols: Set[str] = set(
            [key for key in self._tracking_tasks.keys() if not self._tracking_tasks[key].done()]
        )
        available_pairs: Dict[str, bitroyalOrderBookTrackerEntry] = await self.data_source.get_tracking_pairs()
=======
        tracking_symbols: Set[str] = set([key for key in self._tracking_tasks.keys()
                                          if not self._tracking_tasks[key].done()])
        available_pairs: Dict[str, CoinbaseProOrderBookTrackerEntry] = await self.data_source.get_tracking_pairs()
>>>>>>> Created bitroyal connector folder and files in hummingbot>market
        available_symbols: Set[str] = set(available_pairs.keys())
        new_symbols: Set[str] = available_symbols - tracking_symbols
        deleted_symbols: Set[str] = tracking_symbols - available_symbols

        for symbol in new_symbols:
<<<<<<< HEAD
            order_book_tracker_entry: bitroyalOrderBookTrackerEntry = available_pairs[symbol]
=======
            order_book_tracker_entry: CoinbaseProOrderBookTrackerEntry = available_pairs[symbol]
>>>>>>> Created bitroyal connector folder and files in hummingbot>market
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
<<<<<<< HEAD
                ob_message: bitroyalOrderBookMessage = await self._order_book_diff_stream.get()
=======
                ob_message: CoinbaseProOrderBookMessage = await self._order_book_diff_stream.get()
>>>>>>> Created bitroyal connector folder and files in hummingbot>market
                symbol: str = ob_message.symbol
                if symbol not in self._tracking_message_queues:
                    messages_queued += 1
                    # Save diff messages received before snapshots are ready
                    self._saved_message_queues[symbol].append(ob_message)
                    continue
                message_queue: asyncio.Queue = self._tracking_message_queues[symbol]
                # Check the order book's initial update ID. If it's larger, don't bother.
<<<<<<< HEAD
                order_book: bitroyalOrderBook = self._order_books[symbol]
=======
                order_book: CoinbaseProOrderBook = self._order_books[symbol]
>>>>>>> Created bitroyal connector folder and files in hummingbot>market

                if order_book.snapshot_uid > ob_message.update_id:
                    messages_rejected += 1
                    continue
                await message_queue.put(ob_message)
                messages_accepted += 1

                # Log some statistics.
                now: float = time.time()
                if int(now / 60.0) > int(last_message_timestamp / 60.0):
<<<<<<< HEAD
                    self.logger().debug(
                        "Diff messages processed: %d, rejected: %d, queued: %d",
                        messages_accepted,
                        messages_rejected,
                        messages_queued,
                    )
=======
                    self.logger().debug("Diff messages processed: %d, rejected: %d, queued: %d",
                                       messages_accepted,
                                       messages_rejected,
                                       messages_queued)
>>>>>>> Created bitroyal connector folder and files in hummingbot>market
                    messages_accepted = 0
                    messages_rejected = 0
                    messages_queued = 0

                last_message_timestamp = now
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    f"Unexpected error routing order book messages.",
                    exc_info=True,
<<<<<<< HEAD
                    app_warning_msg=f"Unexpected error routing order book messages. Retrying after 5 seconds.",
=======
                    app_warning_msg=f"Unexpected error routing order book messages. Retrying after 5 seconds."
>>>>>>> Created bitroyal connector folder and files in hummingbot>market
                )
                await asyncio.sleep(5.0)

    async def _track_single_book(self, symbol: str):
<<<<<<< HEAD
        past_diffs_window: Deque[bitroyalOrderBookMessage] = deque()
        self._past_diffs_windows[symbol] = past_diffs_window

        message_queue: asyncio.Queue = self._tracking_message_queues[symbol]
        order_book: bitroyalOrderBook = self._order_books[symbol]
        active_order_tracker: bitroyalActiveOrderTracker = self._active_order_trackers[symbol]
=======
        past_diffs_window: Deque[CoinbaseProOrderBookMessage] = deque()
        self._past_diffs_windows[symbol] = past_diffs_window

        message_queue: asyncio.Queue = self._tracking_message_queues[symbol]
        order_book: CoinbaseProOrderBook = self._order_books[symbol]
        active_order_tracker: CoinbaseProActiveOrderTracker = self._active_order_trackers[symbol]
>>>>>>> Created bitroyal connector folder and files in hummingbot>market

        last_message_timestamp: float = time.time()
        diff_messages_accepted: int = 0

        while True:
            try:
<<<<<<< HEAD
                message: bitroyalOrderBookMessage = None
                saved_messages: Deque[bitroyalOrderBookMessage] = self._saved_message_queues[symbol]
=======
                message: CoinbaseProOrderBookMessage = None
                saved_messages: Deque[CoinbaseProOrderBookMessage] = self._saved_message_queues[symbol]
>>>>>>> Created bitroyal connector folder and files in hummingbot>market
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
<<<<<<< HEAD
                        self.logger().debug("Processed %d order book diffs for %s.", diff_messages_accepted, symbol)
                        diff_messages_accepted = 0
                    last_message_timestamp = now
                elif message.type is OrderBookMessageType.SNAPSHOT:
                    past_diffs: List[bitroyalOrderBookMessage] = list(past_diffs_window)
=======
                        self.logger().debug("Processed %d order book diffs for %s.",
                                           diff_messages_accepted, symbol)
                        diff_messages_accepted = 0
                    last_message_timestamp = now
                elif message.type is OrderBookMessageType.SNAPSHOT:
                    past_diffs: List[CoinbaseProOrderBookMessage] = list(past_diffs_window)
>>>>>>> Created bitroyal connector folder and files in hummingbot>market
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
                self.logger().network(
                    f"Unexpected error processing order book messages for {symbol}.",
                    exc_info=True,
<<<<<<< HEAD
                    app_warning_msg=f"Unexpected error processing order book messages. Retrying after 5 seconds.",
=======
                    app_warning_msg=f"Unexpected error processing order book messages. Retrying after 5 seconds."
>>>>>>> Created bitroyal connector folder and files in hummingbot>market
                )
                await asyncio.sleep(5.0)
