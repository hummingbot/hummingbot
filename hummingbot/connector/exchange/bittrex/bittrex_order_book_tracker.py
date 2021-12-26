#!/usr/bin/env python
import asyncio
import bisect
import logging
import time

from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional, Set

from hummingbot.connector.exchange.bittrex.bittrex_active_order_tracker import BittrexActiveOrderTracker
from hummingbot.connector.exchange.bittrex.bittrex_api_order_book_data_source import BittrexAPIOrderBookDataSource
from hummingbot.connector.exchange.bittrex.bittrex_order_book import BittrexOrderBook
from hummingbot.connector.exchange.bittrex.bittrex_order_book_message import BittrexOrderBookMessage
from hummingbot.connector.exchange.bittrex.bittrex_order_book_tracker_entry import BittrexOrderBookTrackerEntry
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger


class BittrexOrderBookTracker(OrderBookTracker):
    _btobt_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._btobt_logger is None:
            cls._btobt_logger = logging.getLogger(__name__)
        return cls._btobt_logger

    def __init__(self, trading_pairs: List[str]):
        super().__init__(BittrexAPIOrderBookDataSource(trading_pairs), trading_pairs)
        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_diff_stream: asyncio.Queue = asyncio.Queue()
        self._process_msg_deque_task: Optional[asyncio.Task] = None
        self._past_diffs_windows: Dict[str, Deque] = {}
        self._order_books: Dict[str, BittrexOrderBook] = {}
        self._saved_message_queues: Dict[str, Deque[BittrexOrderBookMessage]] = defaultdict(lambda: deque(maxlen=1000))
        self._active_order_trackers: Dict[str, BittrexActiveOrderTracker] = defaultdict(BittrexActiveOrderTracker)

        self._order_book_event_listener_task: Optional[asyncio.Task] = None

    @property
    def exchange_name(self) -> str:
        return "bittrex"

    def start(self):
        super().start()
        self._order_book_event_listener_task = safe_ensure_future(self._data_source.listen_for_subscriptions())

    def stop(self):
        super().stop()
        if self._order_book_event_listener_task is not None:
            self._order_book_event_listener_task.cancel()
            self._order_book_event_listener_task = None

    async def _refresh_tracking_tasks(self):
        """
        Starts tracking for any new trading pairs, and stop tracking for any inactive trading pairs.
        """
        tracking_trading_pair: Set[str] = set(
            [key for key in self._tracking_tasks.keys() if not self._tracking_tasks[key].done()]
        )
        available_pairs: Dict[str, BittrexOrderBookTrackerEntry] = await self.data_source.get_tracking_pairs()
        available_trading_pair: Set[str] = set(available_pairs.keys())
        new_trading_pair: Set[str] = available_trading_pair - tracking_trading_pair
        deleted_trading_pair: Set[str] = tracking_trading_pair - available_trading_pair

        for trading_pair in new_trading_pair:
            order_book_tracker_entry: BittrexOrderBookTrackerEntry = available_pairs[trading_pair]
            self._active_order_trackers[trading_pair] = order_book_tracker_entry.active_order_tracker
            self._order_books[trading_pair] = order_book_tracker_entry.order_book
            self._tracking_message_queues[trading_pair] = asyncio.Queue()
            self._tracking_tasks[trading_pair] = safe_ensure_future(self._track_single_book(trading_pair))
            self.logger().info(f"Started order book tracking for {trading_pair}.")

        for trading_pair in deleted_trading_pair:
            self._tracking_tasks[trading_pair].cancel()
            del self._tracking_tasks[trading_pair]
            del self._order_books[trading_pair]
            del self._active_order_trackers[trading_pair]
            del self._tracking_message_queues[trading_pair]
            self.logger().info(f"Stopped order book tracking for {trading_pair}.")

    async def _order_book_diff_router(self):
        """
        Route the real-time order book diff messages to the correct order book.
        """
        last_message_timestamp: float = time.time()
        message_queued: int = 0
        message_accepted: int = 0
        message_rejected: int = 0
        while True:
            try:
                ob_message: BittrexOrderBookMessage = await self._order_book_diff_stream.get()
                trading_pair: str = ob_message.trading_pair
                if trading_pair not in self._tracking_message_queues:
                    message_queued += 1
                    # Save diff messages received before snaphsots are ready
                    self._saved_message_queues[trading_pair].append(ob_message)
                    continue
                message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
                # Check the order book's initial update ID. If it's larger, don't bother.
                order_book: BittrexOrderBook = self._order_books[trading_pair]

                if order_book.snapshot_uid > ob_message.update_id:
                    message_rejected += 1
                    continue
                await message_queue.put(ob_message)
                message_accepted += 1

                # Log some statistics
                now: float = time.time()
                if int(now / 60.0) > int(last_message_timestamp / 60.0):
                    self.logger().debug(
                        f"Diff message processed: "
                        f"{message_accepted}, "
                        f"rejected: {message_rejected}, "
                        f"queued: {message_queue}"
                    )
                    message_accepted = 0
                    message_rejected = 0
                    message_queued = 0

                last_message_timestamp = now

            except asyncio.CancelledError:
                raise

            except Exception:
                self.logger().network(
                    "Unexpected error routing order book messages.",
                    exc_info=True,
                    app_warning_msg="Unexpected error routing order book messages. Retrying after 5 seconds.",
                )
                await asyncio.sleep(5.0)

    async def _track_single_book(self, trading_pair: str):
        past_diffs_window: Deque[BittrexOrderBookMessage] = deque()
        self._past_diffs_windows[trading_pair] = past_diffs_window

        message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
        order_book: BittrexOrderBook = self._order_books[trading_pair]
        active_order_tracker: BittrexActiveOrderTracker = self._active_order_trackers[trading_pair]

        last_message_timestamp = order_book.snapshot_uid
        diff_message_accepted: int = 0

        while True:
            try:
                message: BittrexOrderBookMessage = None
                save_messages: Deque[BittrexOrderBookMessage] = self._saved_message_queues[trading_pair]
                # Process saved messages first if there are any
                if len(save_messages) > 0:
                    message = save_messages.popleft()
                elif message_queue.qsize() > 0:
                    message = await message_queue.get()
                else:
                    # Waits to received some diff messages
                    await asyncio.sleep(3)
                    continue

                # Processes diff stream
                if message.type is OrderBookMessageType.DIFF:

                    bids, asks = active_order_tracker.convert_diff_message_to_order_book_row(message)
                    order_book.apply_diffs(bids, asks, message.update_id)
                    past_diffs_window.append(message)
                    while len(past_diffs_window) > self.PAST_DIFF_WINDOW_SIZE:
                        past_diffs_window.popleft()
                    diff_message_accepted += 1

                    # Output some statistics periodically.
                    now: float = message.update_id
                    if now > last_message_timestamp:
                        self.logger().debug(f"Processed {diff_message_accepted} order book diffs for {trading_pair}")
                        diff_message_accepted = 0
                    last_message_timestamp = now
                # Processes snapshot stream
                elif message.type is OrderBookMessageType.SNAPSHOT:
                    past_diffs: List[BittrexOrderBookMessage] = list(past_diffs_window)
                    # only replay diffs later than snapshot, first update active order with snapshot then replay diffs
                    replay_position = bisect.bisect_right(past_diffs, message)
                    replay_diffs = past_diffs[replay_position:]
                    s_bids, s_asks = active_order_tracker.convert_snapshot_message_to_order_book_row(message)
                    order_book.apply_snapshot(s_bids, s_asks, message.update_id)
                    for diff_message in replay_diffs:
                        d_bids, d_asks = active_order_tracker.convert_diff_message_to_order_book_row(diff_message)
                        order_book.apply_diffs(d_bids, d_asks, diff_message.update_id)

                    self.logger().debug(f"Processed order book snapshot for {trading_pair}.")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    f"Unexpected error processing order book messages for {trading_pair}.",
                    exc_info=True,
                    app_warning_msg="Unexpected error processing order book messages. Retrying after 5 seconds.",
                )
                await asyncio.sleep(5.0)
