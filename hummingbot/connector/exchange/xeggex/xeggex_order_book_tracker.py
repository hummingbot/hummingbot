#!/usr/bin/env python
import asyncio
import bisect
import logging
import time
from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional

import numpy as np

from hummingbot.connector.exchange.xeggex.xeggex_api_order_book_data_source import XeggexAPIOrderBookDataSource
from hummingbot.connector.exchange.xeggex.xeggex_constants import Constants
from hummingbot.connector.exchange.xeggex.xeggex_order_book import XeggexOrderBook
from hummingbot.connector.exchange.xeggex.xeggex_order_book_message import XeggexOrderBookMessage
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.logger import HummingbotLogger

s_empty_diff = np.ndarray(shape=(0, 4), dtype="float64")


class XeggexOrderBookTracker(OrderBookTracker):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pairs: Optional[List[str]] = None,):
        super().__init__(XeggexAPIOrderBookDataSource(trading_pairs), trading_pairs)

        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_diff_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_trade_stream: asyncio.Queue = asyncio.Queue()
        self._process_msg_deque_task: Optional[asyncio.Task] = None
        self._past_diffs_windows: Dict[str, Deque] = {}
        self._order_books: Dict[str, XeggexOrderBook] = {}
        self._saved_message_queues: Dict[str, Deque[XeggexOrderBookMessage]] = \
            defaultdict(lambda: deque(maxlen=1000))
        self._order_book_stream_listener_task: Optional[asyncio.Task] = None
        self._order_book_trade_listener_task: Optional[asyncio.Task] = None

    @property
    def exchange_name(self) -> str:
        """
        Name of the current exchange
        """
        return Constants.EXCHANGE_NAME

    async def _track_single_book(self, trading_pair: str):
        """
        Update an order book with changes from the latest batch of received messages
        """
        past_diffs_window: Deque[XeggexOrderBookMessage] = deque()
        self._past_diffs_windows[trading_pair] = past_diffs_window

        message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
        order_book: XeggexOrderBook = self._order_books[trading_pair]

        last_message_timestamp: float = time.time()
        diff_messages_accepted: int = 0

        while True:
            try:
                message: XeggexOrderBookMessage = None
                saved_messages: Deque[XeggexOrderBookMessage] = self._saved_message_queues[trading_pair]
                # Process saved messages first if there are any
                if len(saved_messages) > 0:
                    message = saved_messages.popleft()
                else:
                    message = await message_queue.get()

                if message.type is OrderBookMessageType.DIFF:
                    # new method
                    mbids = message.content.get('bids')
                    masks = message.content.get('asks')

                    smsg = str(mbids)
                    self.logger().info(f"TESTING3... {smsg}.")

                    np_bids = s_empty_diff
                    np_asks = s_empty_diff

                    if len(mbids) > 0:
                        if (isinstance(mbids[0], list)):
                            np_bids = np.array(
                                [[message.timestamp,
                                    float(bid[0]),
                                    float(bid[1]),
                                    message.update_id]
                                    for bid in mbids], dtype='float64', ndmin=2)
                        else:
                            np_bids = np.array(
                                [[message.timestamp,
                                    float(bid["price"]),
                                    float(bid["quantity"]),
                                    message.update_id]
                                    for bid in mbids], dtype='float64', ndmin=2)

                    if len(masks) > 0:
                        if (isinstance(mbids[0], list)):
                            np_asks = np.array(
                                [[message.timestamp,
                                    float(ask[0]),
                                    float(ask[1]),
                                    message.update_id]
                                    for ask in masks], dtype='float64', ndmin=2)
                        else:
                            np_asks = np.array(
                                [[message.timestamp,
                                    float(ask["price"]),
                                    float(ask["quantity"]),
                                    message.update_id]
                                    for ask in masks], dtype='float64', ndmin=2)

                    d_bids = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_bids]
                    d_asks = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_asks]

                    order_book.apply_diffs(d_bids, d_asks, message.update_id)
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
                    past_diffs: List[XeggexOrderBookMessage] = list(past_diffs_window)
                    # only replay diffs later than snapshot, first update active order with snapshot then replay diffs
                    replay_position = bisect.bisect_right(past_diffs, message)
                    replay_diffs = past_diffs[replay_position:]

                    mbids = message.content.get('bids')
                    masks = message.content.get('asks')

                    smsg = str(mbids)
                    self.logger().info(f"TESTING2... {smsg}.")

                    np_bids = s_empty_diff
                    np_asks = s_empty_diff

                    if len(mbids) > 0:
                        if (isinstance(mbids[0], list)):
                            np_bids = np.array(
                                [[message.timestamp,
                                    float(bid[0]),
                                    float(bid[1]),
                                    message.update_id]
                                    for bid in mbids], dtype='float64', ndmin=2)
                        else:
                            np_bids = np.array(
                                [[message.timestamp,
                                    float(bid["price"]),
                                    float(bid["quantity"]),
                                    message.update_id]
                                    for bid in mbids], dtype='float64', ndmin=2)

                    if len(masks) > 0:
                        if (isinstance(mbids[0], list)):
                            np_asks = np.array(
                                [[message.timestamp,
                                    float(ask[0]),
                                    float(ask[1]),
                                    message.update_id]
                                    for ask in masks], dtype='float64', ndmin=2)
                        else:
                            np_asks = np.array(
                                [[message.timestamp,
                                    float(ask["price"]),
                                    float(ask["quantity"]),
                                    message.update_id]
                                    for ask in masks], dtype='float64', ndmin=2)

                    s_bids = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_bids]
                    s_asks = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_asks]

                    order_book.apply_snapshot(s_bids, s_asks, message.update_id)
                    for diff_message in replay_diffs:
                        mbids = diff_message.content.get('bids')
                        masks = diff_message.content.get('asks')

                        smsg = str(mbids)
                        self.logger().info(f"TESTING4... {smsg}.")

                        np_bids = s_empty_diff
                        np_asks = s_empty_diff

                        if len(mbids) > 0:
                            if (isinstance(mbids[0], list)):
                                np_bids = np.array(
                                    [[diff_message.timestamp,
                                        float(bid[0]),
                                        float(bid[1]),
                                        diff_message.update_id]
                                        for bid in mbids], dtype='float64', ndmin=2)
                            else:
                                np_bids = np.array(
                                    [[diff_message.timestamp,
                                        float(bid["price"]),
                                        float(bid["quantity"]),
                                        diff_message.update_id]
                                        for bid in mbids], dtype='float64', ndmin=2)

                        if len(masks) > 0:
                            if (isinstance(mbids[0], list)):
                                np_asks = np.array(
                                    [[diff_message.timestamp,
                                        float(ask[0]),
                                        float(ask[1]),
                                        diff_message.update_id]
                                        for ask in masks], dtype='float64', ndmin=2)
                            else:
                                np_asks = np.array(
                                    [[diff_message.timestamp,
                                        float(ask["price"]),
                                        float(ask["quantity"]),
                                        diff_message.update_id]
                                        for ask in masks], dtype='float64', ndmin=2)

                        d_bids = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_bids]
                        d_asks = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_asks]
                        order_book.apply_diffs(d_bids, d_asks, diff_message.update_id)

                    self.logger().debug(f"Processed order book snapshot for {trading_pair}.")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    f"Unexpected error processing order book messages for {trading_pair}.",
                    exc_info=True,
                    app_warning_msg="Unexpected error processing order book messages. Retrying after 5 seconds."
                )
                await asyncio.sleep(5.0)
