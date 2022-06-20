#!/usr/bin/env python

import asyncio
import bisect
import logging
import time
from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional

from hummingbot.connector.exchange.coinex.coinex_active_order_tracker import \
    CoinexActiveOrderTracker
from hummingbot.connector.exchange.coinex.coinex_api_order_book_data_source import \
    CoinexAPIOrderBookDataSource
from hummingbot.connector.exchange.coinex.coinex_order_book import \
    CoinexOrderBook
from hummingbot.connector.exchange.coinex.coinex_order_book_message import \
    CoinexOrderBookMessage
from hummingbot.core.data_type.order_book_message import (OrderBookMessage,
                                                          OrderBookMessageType)
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.event.events import TradeType
from hummingbot.logger import HummingbotLogger


class CoinexOrderBookTracker(OrderBookTracker):
    _cbpobt_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._cbpobt_logger is None:
            cls._cbpobt_logger = logging.getLogger(__name__)
        return cls._cbpobt_logger

    def __init__(self,
                 trading_pairs: Optional[List[str]] = None):
        super().__init__(data_source=CoinexAPIOrderBookDataSource(trading_pairs=trading_pairs),
                         trading_pairs=trading_pairs)
        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_diff_stream: asyncio.Queue = asyncio.Queue()
        self._process_msg_deque_task: Optional[asyncio.Task] = None
        self._past_diffs_windows: Dict[str, Deque] = {}
        self._order_books: Dict[str, CoinexOrderBook] = {}
        self._saved_message_queues: Dict[str, Deque[CoinexOrderBookMessage]] = defaultdict(lambda: deque(maxlen=1000))
        self._active_order_trackers: Dict[str, CoinexActiveOrderTracker] = defaultdict(CoinexActiveOrderTracker)

    @property
    def exchange_name(self) -> str:
        """
        *required
        Name of the current exchange
        """
        return "coinex"

    async def _order_book_diff_router(self) -> None:
        """
        Route the real-time order book diff messages to the correct order book.
        """
        last_message_timestamp: float = time.time()
        messages_queued: int = 0
        messages_accepted: int = 0
        messages_rejected: int = 0
        while True:
            try:
                ob_message: CoinexOrderBookMessage = await self._order_book_diff_stream.get()
                trading_pair: str = ob_message.trading_pair
                if trading_pair not in self._tracking_message_queues:
                    messages_queued += 1
                    # Save diff messages received before snapshots are ready
                    self._saved_message_queues[trading_pair].append(ob_message)
                    continue
                message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
                # Check the order book's initial update ID. If it's larger, don't bother.
                order_book: CoinexOrderBook = self._order_books[trading_pair]
                if order_book.snapshot_uid > ob_message.update_id:
                    messages_rejected += 1
                    continue
                await message_queue.put(ob_message)
                messages_accepted += 1

                # Log some statistics.
                now: float = time.time()
                if int(now / 60.0) > int(last_message_timestamp / 60.0):
                    # TODO: REVERT TO debug
                    self.logger().info(f"Diff messages processed: {messages_accepted}, "
                                       f"rejected: {messages_rejected}, queued: {messages_queued}")
                    messages_accepted = 0
                    messages_rejected = 0
                    messages_queued = 0

                last_message_timestamp = now
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    f'{"Unexpected error routing order book messages."}',
                    exc_info=True,
                    app_warning_msg=f'{"Unexpected error routing order book messages. Retrying after 5 seconds."}'
                )
                await asyncio.sleep(5.0)

    async def _track_single_book(self, trading_pair: str) -> None:
        """
        Update an order book with changes from the latest batch of received messages
        """
        past_diffs_window: Deque[CoinexOrderBookMessage] = deque()
        self._past_diffs_windows[trading_pair] = past_diffs_window

        message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
        order_book: CoinexOrderBook = self._order_books[trading_pair]
        active_order_tracker: CoinexActiveOrderTracker = self._active_order_trackers[trading_pair]

        last_message_timestamp: float = time.time()
        diff_messages_accepted: int = 0

        while True:
            try:
                message: CoinexOrderBookMessage
                saved_messages: Deque[CoinexOrderBookMessage] = self._saved_message_queues[trading_pair]
                # Process saved messages first if there are any
                if len(saved_messages) > 0:
                    message = saved_messages.popleft()
                else:
                    message = await message_queue.get()

                if message.type is OrderBookMessageType.DIFF:
                    # TODO: Review me, sometimes our messages don't return with bids / asks.
                    if "bids" not in message.content:
                        message.content["bids"] = []
                    if "asks" not in message.content:
                        message.content["asks"] = []
                    bids, asks = active_order_tracker.convert_diff_message_to_order_book_row(message)
                    order_book.apply_diffs(bids, asks, message.update_id)
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
                    past_diffs: List[CoinexOrderBookMessage] = list(past_diffs_window)
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
                    app_warning_msg=f'{"Unexpected error processing order book messages. Retrying after 5 seconds."}'
                )
                await asyncio.sleep(5.0)
