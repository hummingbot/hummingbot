#!/usr/bin/env python
import asyncio
import bisect
import logging
import time
from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional

import aiohttp

import hummingbot.connector.exchange.xago_io.xago_io_constants as constants
from hummingbot.connector.exchange.xago_io.xago_io_active_order_tracker import XagoIoActiveOrderTracker
from hummingbot.connector.exchange.xago_io.xago_io_api_order_book_data_source import XagoIoAPIOrderBookDataSource
from hummingbot.connector.exchange.xago_io.xago_io_order_book import XagoIoOrderBook
from hummingbot.connector.exchange.xago_io.xago_io_order_book_message import XagoIoOrderBookMessage
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.xago_io.xago_io_auth import XagoIoAuth


class XagoIoOrderBookTracker(OrderBookTracker):
    def __init__(self, trading_pairs: List[str], auth: XagoIoAuth, shared_client: Optional[aiohttp.ClientSession] = None):
        super().__init__(
            data_source=XagoIoAPIOrderBookDataSource(trading_pairs, auth, shared_client),
            trading_pairs=trading_pairs
        )

        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._process_msg_deque_task: Optional[asyncio.Task] = None
        self._past_diffs_windows: Dict[str, Deque] = {}
        self._order_books: Dict[str, XagoIoOrderBook] = {}
        self._saved_message_queues: Dict[str, Deque[XagoIoOrderBookMessage]] = defaultdict(
            lambda: deque(maxlen=1000)
        )
        self._active_order_trackers: Dict[str, XagoIoActiveOrderTracker] = defaultdict(XagoIoActiveOrderTracker)
        self._order_book_stream_listener_task: Optional[asyncio.Task] = None
        self._order_book_trade_listener_task: Optional[asyncio.Task] = None

    @property
    def exchange_name(self) -> str:
        """
        Name of the current exchange
        """
        return constants.EXCHANGE_NAME

    def start(self):
        super().start()
        self._order_book_stream_listener_task = safe_ensure_future(self._data_source.listen_for_subscriptions())

    def stop(self):
        self._order_book_stream_listener_task and self._order_book_stream_listener_task.cancel()
        super().stop()

    async def _track_single_book(self, trading_pair: str):
        """
        Update an order book with changes from the latest batch of received messages
        """
        past_diffs_window: Deque[XagoIoOrderBookMessage] = deque()
        self._past_diffs_windows[trading_pair] = past_diffs_window

        message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
        order_book: XagoIoOrderBook = self._order_books[trading_pair]
        active_order_tracker: XagoIoActiveOrderTracker = self._active_order_trackers[trading_pair]

        last_message_timestamp: float = time.time()
        diff_messages_accepted: int = 0

        while True:
            try:
                message = await message_queue.get()

                if message.type is OrderBookMessageType.DIFF:
                    try:
                        bids, asks = active_order_tracker.convert_diff_message_to_order_book_row(message)
                        order_book.apply_diffs(bids, asks, message.update_id)
                    except Exception as e:
                        self.logger().error(f"Error converting DIFF message: {e}")
                elif message.type is OrderBookMessageType.SNAPSHOT:
                    past_diffs: List[XagoIoOrderBookMessage] = list(past_diffs_window)
                    # only replay diffs later than snapshot, first update active order with snapshot then replay diffs
                    replay_position = bisect.bisect_right(past_diffs, message)
                    replay_diffs = past_diffs[replay_position:]
                    s_bids, s_asks = active_order_tracker.convert_snapshot_message_to_order_book_row(message)
                    order_book.apply_snapshot(s_bids, s_asks, message.update_id)
                    for diff_message in replay_diffs:
                        d_bids, d_asks = active_order_tracker.convert_diff_message_to_order_book_row(diff_message)
                        order_book.apply_diffs(d_bids, d_asks, diff_message.update_id)
            except asyncio.CancelledError as e:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error tracking order book for {trading_pair}. Error: {e}")
                await asyncio.sleep(5.0)
