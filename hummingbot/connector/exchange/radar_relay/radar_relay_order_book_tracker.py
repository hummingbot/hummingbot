#!/usr/bin/env python

import asyncio
import bisect
from collections import deque, defaultdict
import logging
import time
from typing import (
    Deque,
    Dict,
    List,
    Optional,
    Set
)

from hummingbot.core.event.events import TradeType
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.connector.exchange.radar_relay.radar_relay_api_order_book_data_source import RadarRelayAPIOrderBookDataSource
from hummingbot.connector.exchange.radar_relay.radar_relay_order_book_message import RadarRelayOrderBookMessage
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessageType,
    OrderBookMessage,
)
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.connector.exchange.radar_relay.radar_relay_order_book import RadarRelayOrderBook
from hummingbot.connector.exchange.radar_relay.radar_relay_active_order_tracker import RadarRelayActiveOrderTracker
from hummingbot.connector.exchange.radar_relay.radar_relay_order_book_tracker_entry import RadarRelayOrderBookTrackerEntry


class RadarRelayOrderBookTracker(OrderBookTracker):
    _rrobt_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._rrobt_logger is None:
            cls._rrobt_logger = logging.getLogger(__name__)
        return cls._rrobt_logger

    def __init__(self, trading_pairs: List[str]):
        super().__init__(RadarRelayAPIOrderBookDataSource(trading_pairs), trading_pairs)
        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_diff_stream: asyncio.Queue = asyncio.Queue()
        self._process_msg_deque_task: Optional[asyncio.Task] = None
        self._past_diffs_windows: Dict[str, Deque] = {}
        self._order_books: Dict[str, RadarRelayOrderBook] = {}
        self._saved_message_queues: Dict[str, Deque[RadarRelayOrderBookMessage]] = defaultdict(lambda: deque(maxlen=1000))
        self._active_order_trackers: Dict[str, RadarRelayActiveOrderTracker] = defaultdict(RadarRelayActiveOrderTracker)

    @property
    def exchange_name(self) -> str:
        return "radar_relay"

    async def _refresh_tracking_tasks(self):
        """
        Starts tracking for any new trading pairs, and stop tracking for any inactive trading pairs.
        """
        tracking_trading_pairs: Set[str] = set([key for key in self._tracking_tasks.keys()
                                               if not self._tracking_tasks[key].done()])
        available_pairs: Dict[str, RadarRelayOrderBookTrackerEntry] = await self.data_source.get_tracking_pairs()
        available_trading_pairs: Set[str] = set(available_pairs.keys())
        new_trading_pairs: Set[str] = available_trading_pairs - tracking_trading_pairs
        deleted_trading_pairs: Set[str] = tracking_trading_pairs - available_trading_pairs

        for trading_pair in new_trading_pairs:
            order_book_tracker_entry: RadarRelayOrderBookTrackerEntry = available_pairs[trading_pair]
            self._active_order_trackers[trading_pair] = order_book_tracker_entry.active_order_tracker
            self._order_books[trading_pair] = order_book_tracker_entry.order_book
            self._tracking_message_queues[trading_pair] = asyncio.Queue()
            self._tracking_tasks[trading_pair] = safe_ensure_future(self._track_single_book(trading_pair))
            self.logger().info("Started order book tracking for %s." % trading_pair)

        for trading_pair in deleted_trading_pairs:
            self._tracking_tasks[trading_pair].cancel()
            del self._tracking_tasks[trading_pair]
            del self._order_books[trading_pair]
            del self._active_order_trackers[trading_pair]
            del self._tracking_message_queues[trading_pair]
            self.logger().info("Stopped order book tracking for %s." % trading_pair)

    async def _order_book_diff_router(self):
        """
        Route the real-time order book diff messages to the correct order book.
        """
        last_message_timestamp: float = time.time()
        messages_queued: int = 0
        messages_accepted: int = 0
        messages_rejected: int = 0
        address_token_map: Dict[str, any] = await self._data_source.get_all_token_info()
        while True:
            try:
                ob_message: RadarRelayOrderBookMessage = await self._order_book_diff_stream.get()
                base_token_address: str = ob_message.content["event"]["baseTokenAddress"]
                quote_token_address: str = ob_message.content["event"]["quoteTokenAddress"]
                base_token_asset: str = address_token_map[base_token_address]["symbol"]
                quote_token_asset: str = address_token_map[quote_token_address]['symbol']
                trading_pair: str = f"{base_token_asset}-{quote_token_asset}"

                if trading_pair not in self._tracking_message_queues:
                    messages_queued += 1
                    # Save diff messages received before snapshots are ready
                    self._saved_message_queues[trading_pair].append(ob_message)
                    continue
                message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
                # Check the order book's initial update ID. If it's larger, don't bother.
                order_book: RadarRelayOrderBook = self._order_books[trading_pair]

                if order_book.snapshot_uid > ob_message.update_id:
                    messages_rejected += 1
                    continue
                await message_queue.put(ob_message)

                if ob_message.content["action"] == "FILL":  # put FILL messages to trade queue
                    trade_type = float(TradeType.BUY.value) if ob_message.content["event"]["type"] == "BUY" \
                        else float(TradeType.SELL.value)
                    self._order_book_trade_stream.put_nowait(OrderBookMessage(OrderBookMessageType.TRADE, {
                        "trading_pair": trading_pair,
                        "trade_type": trade_type,
                        "trade_id": ob_message.update_id,
                        "update_id": ob_message.timestamp,
                        "price": ob_message.content["event"]["order"]["price"],
                        "amount": ob_message.content["event"]["filledBaseTokenAmount"]
                    }, timestamp=ob_message.timestamp))

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
                    exc_info=True,
                    app_warning_msg="Unexpected error routing order book messages. Retrying after 5 seconds."
                )
                await asyncio.sleep(5.0)

    async def _track_single_book(self, trading_pair: str):
        past_diffs_window: Deque[RadarRelayOrderBookMessage] = deque()
        self._past_diffs_windows[trading_pair] = past_diffs_window

        message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
        order_book: RadarRelayOrderBook = self._order_books[trading_pair]
        active_order_tracker: RadarRelayActiveOrderTracker = self._active_order_trackers[trading_pair]

        last_message_timestamp: float = time.time()
        diff_messages_accepted: int = 0

        while True:
            try:
                message: RadarRelayOrderBookMessage = None
                saved_messages: Deque[RadarRelayOrderBookMessage] = self._saved_message_queues[trading_pair]
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
                        self.logger().debug(f"Processed {diff_messages_accepted} order book diffs for {trading_pair}.")
                        diff_messages_accepted = 0
                    last_message_timestamp = now
                elif message.type is OrderBookMessageType.SNAPSHOT:
                    past_diffs: List[RadarRelayOrderBookMessage] = list(past_diffs_window)
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
                    f"Unexpected error tracking order book for {trading_pair}.",
                    exc_info=True,
                    app_warning_msg="Unexpected error tracking order book. Retrying after 5 seconds."
                )
                await asyncio.sleep(5.0)
