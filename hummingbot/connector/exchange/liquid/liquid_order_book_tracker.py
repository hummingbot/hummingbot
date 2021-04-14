#!/usr/bin/env python

import asyncio
import logging
import time
from collections import deque, defaultdict
from typing import (
    Deque,
    Dict,
    List,
    Optional
)

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from hummingbot.connector.exchange.liquid.liquid_api_order_book_data_source import LiquidAPIOrderBookDataSource
from hummingbot.logger import HummingbotLogger


class LiquidOrderBookTracker(OrderBookTracker):
    _lobt_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> (HummingbotLogger):
        if cls._lobt_logger is None:
            cls._lobt_logger = logging.getLogger(__name__)
        return cls._lobt_logger

    def __init__(self, trading_pairs: List[str]):
        super().__init__(LiquidAPIOrderBookDataSource(trading_pairs), trading_pairs)
        self._order_book_diff_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()
        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._saved_message_queues: Dict[str, Deque[OrderBookMessage]] = defaultdict(lambda: deque(maxlen=1000))

    @property
    def exchange_name(self) -> (str):
        return "liquid"

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
                ob_message: OrderBookMessage = await self._order_book_diff_stream.get()

                trading_pair: str = ob_message.trading_pair
                if trading_pair not in self._tracking_message_queues:
                    messages_queued += 1
                    # Save diff messages received before snapshots are ready
                    self._saved_message_queues[trading_pair].append(ob_message)
                    continue
                message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
                # Check the order book's initial update ID. If it's larger, don't bother.
                order_book: OrderBook = self._order_books[trading_pair]
                if order_book.snapshot_uid > ob_message.update_id:
                    messages_rejected += 1
                    continue
                # Liquid order_book diff message does not contain entries to be deleted, it is actually a snapshot with
                # just one side of the book (either bids or asks), we have to manually check for existing entries here
                # and include them with 0 amount.
                if "asks" in ob_message.content and len(ob_message.content["asks"]) > 0:
                    for price in order_book.snapshot[1].price:
                        if price not in [float(p[0]) for p in ob_message.content["asks"]]:
                            ob_message.content["asks"].append([str(price), str(0)])
                elif "bids" in ob_message.content and len(ob_message.content["bids"]) > 0:
                    for price in order_book.snapshot[0].price:
                        if price not in [float(p[0]) for p in ob_message.content["bids"]]:
                            ob_message.content["bids"].append([str(price), str(0)])
                await message_queue.put(ob_message)
                messages_accepted += 1

                # Log some statistics.
                now: float = time.time()
                if int(now / 60.0) > int(last_message_timestamp / 60.0):
                    self.logger().debug(f"Diff messages processed: {messages_accepted}, "
                                        f"rejected: {messages_rejected}, queued: {messages_queued}")
                    messages_accepted = 0
                    messages_rejected = 0
                    messages_queued = 0

                last_message_timestamp = now
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error routing order book messages.",
                    exec_info=True,
                    app_warning_msg="Unexpected error routing order book messages. Retrying after 5 seconds."
                )
                await asyncio.sleep(5.0)

    async def _order_book_snapshot_router(self):
        """
        Route the real-time order book snapshot messages to the correct order book.
        """
        while True:
            try:
                ob_message: OrderBookMessage = await self._order_book_snapshot_stream.get()
                trading_pair: str = ob_message.trading_pair
                if trading_pair not in self._tracking_message_queues:
                    continue
                message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
                await message_queue.put(ob_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unknown error. Retrying after 5 seconds.", exc_info=True)
                await asyncio.sleep(5.0)

    async def _track_single_book(self, trading_pair: str):
        past_diffs_window: Deque[OrderBookMessage] = deque()
        self._past_diffs_windows[trading_pair] = past_diffs_window

        message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
        order_book: OrderBook = self._order_books[trading_pair]
        last_message_timestamp: float = time.time()
        diff_messages_accepted: int = 0

        while True:
            try:
                message: OrderBookMessage = None
                saved_messages: Deque[OrderBookMessage] = self._saved_message_queues[trading_pair]

                # Process saved messages first if there are any
                if len(saved_messages) > 0:
                    message = saved_messages.popleft()
                else:
                    message = await message_queue.get()

                if message.type is OrderBookMessageType.DIFF:
                    order_book.apply_diffs(message.bids, message.asks, message.update_id)
                    past_diffs_window.append(message)
                    while len(past_diffs_window) > self.PAST_DIFF_WINDOW_SIZE:
                        past_diffs_window.popleft()
                    diff_messages_accepted += 1
                    # Output some statistics periodically.
                    now: float = time.time()
                    if int(now / 60.0) > int(last_message_timestamp / 60.0):
                        self.logger().debug(f"Processed {diff_messages_accepted} order book diffs for {trading_pair}.")
                        diff_messages_accepted = 0
                    last_message_timestamp = now
                elif message.type is OrderBookMessageType.SNAPSHOT:
                    past_diffs: List[OrderBookMessage] = list(past_diffs_window)
                    past_diffs_window.append(message)
                    order_book.restore_from_snapshot_and_diffs(message, past_diffs)
                    self.logger().debug(f"Processed order book snapshot for {trading_pair}.")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    f"Unexpected error tracking order book for {trading_pair}",
                    exec_info=True,
                    app_warning_msg="Unexpected error tracking order book. Retrying ater 5 seconds."
                )
                await asyncio.sleep(5.0)
