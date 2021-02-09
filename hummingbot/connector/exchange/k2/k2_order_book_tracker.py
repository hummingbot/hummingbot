#!/usr/bin/env python
import asyncio
import bisect
import logging
import hummingbot.connector.exchange.k2.k2_constants as constants
import time

from collections import defaultdict, deque
from typing import (
    Dict,
    Deque,
    List,
    Optional,
)

from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.k2.k2_api_order_book_data_source import K2APIOrderBookDataSource
from hummingbot.connector.exchange.k2.k2_order_book import K2OrderBook
from hummingbot.connector.exchange.k2.k2_order_book_message import K2OrderBookMessage
from hummingbot.connector.exchange.k2.k2_utils import (
    convert_diff_message_to_order_book_row,
    convert_snapshot_message_to_order_book_row
)


class K2OrderBookTracker(OrderBookTracker):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pairs: Optional[List[str]] = None):
        super().__init__(data_source=K2APIOrderBookDataSource(trading_pairs),
                         trading_pairs=trading_pairs)

        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_diff_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_trade_stream: asyncio.Queue = asyncio.Queue()
        self._order_books: Dict[str, K2OrderBook] = {}

        self._process_msg_deque_task: Optional[asyncio.Task] = None
        self._past_diff_windows: Dict[str, Deque] = {}
        self._saved_message_queues: Dict[str, Deque[K2OrderBookMessage]] = \
            defaultdict(lambda: Deque(maxlen=1000))

        self._order_book_diff_listener_task: Optional[asyncio.Task] = None
        self._order_book_trade_listner_task: Optional[asyncio.Task] = None

    @property
    def exchange_name(self) -> str:
        """
        Name of the current exchange
        """
        return constants.EXCHANGE_NAME

    async def _track_single_book(self, trading_pair):
        """
        Update an order book with changes from the latest branch of received messages
        """
        pass_diffs_window: Deque[K2OrderBookMessage] = deque()
        self._past_diff_windows[trading_pair] = pass_diffs_window

        message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
        order_book: K2OrderBook = self._order_books[trading_pair]

        last_message_timestamp: float = time.time()
        diff_messages_accepted: int = 0

        while True:
            try:
                message: K2OrderBookMessage = None
                saved_messages: Deque[K2OrderBookMessage] = self._saved_message_queues[trading_pair]
                # Process saved messages first if there are any
                if len(saved_messages) > 0:
                    message = saved_messages.pop_left()
                else:
                    message = await message_queue.get()

                if message.type is OrderBookMessageType.DIFF:
                    bids, asks = convert_diff_message_to_order_book_row(message)
                    order_book.apply_diffs(bids, asks, message.update_id)
                    pass_diffs_window.append(message)
                    while(len(pass_diffs_window) > self.PAST_DIFF_WINDOW_SIZE):
                        pass_diffs_window.popleft()
                    diff_messages_accepted += 1

                    # Output some statistics periodically
                    now: float = time.time()
                    if int(now / 60.0) > int(last_message_timestamp / 60.0):
                        self.logger().debug("Processed %d order book diffs for %s.",
                                            diff_messages_accepted, trading_pair)
                        diff_messages_accepted = 0
                    last_message_timestamp = now
                elif message.type is OrderBookMessageType.SNAPSHOT:
                    past_diffs: List[K2OrderBookMessage] = list(pass_diffs_window)
                    # Only replay diffs later than snapshot
                    replay_position: int = bisect.bisect_right(past_diffs, message)
                    replay_diffs: List[K2OrderBookMessage] = past_diffs[replay_position:]

                    s_bids, s_asks = convert_snapshot_message_to_order_book_row(message)
                    order_book.apply_snapshot(s_bids, s_asks, message.update_id)
                    for diff_message in replay_diffs:
                        d_bids, d_asks = convert_diff_message_to_order_book_row(diff_message)
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
