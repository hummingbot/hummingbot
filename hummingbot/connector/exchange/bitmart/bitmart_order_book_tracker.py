#!/usr/bin/env python
import asyncio
import bisect
import logging
from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional

import hummingbot.connector.exchange.bitmart.bitmart_constants as constants
from hummingbot.connector.exchange.bitmart import bitmart_utils
from hummingbot.connector.exchange.bitmart.bitmart_api_order_book_data_source import BitmartAPIOrderBookDataSource
from hummingbot.connector.exchange.bitmart.bitmart_order_book import BitmartOrderBook
from hummingbot.connector.exchange.bitmart.bitmart_order_book_message import BitmartOrderBookMessage
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger


class BitmartOrderBookTracker(OrderBookTracker):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 throttler: Optional[AsyncThrottler] = None,
                 trading_pairs: Optional[List[str]] = None,
                 api_factory: Optional[WebAssistantsFactory] = None):
        super().__init__(BitmartAPIOrderBookDataSource(throttler, trading_pairs, api_factory), trading_pairs)

        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._api_factory = api_factory
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_diff_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_trade_stream: asyncio.Queue = asyncio.Queue()
        self._process_msg_deque_task: Optional[asyncio.Task] = None
        self._past_diffs_windows: Dict[str, Deque] = {}
        self._order_books: Dict[str, BitmartOrderBook] = {}
        self._saved_message_queues: Dict[str, Deque[BitmartOrderBookMessage]] = \
            defaultdict(lambda: deque(maxlen=1000))
        self._order_book_stream_listener_task: Optional[asyncio.Task] = None
        self._order_book_trade_listener_task: Optional[asyncio.Task] = None

    @property
    def exchange_name(self) -> str:
        """
        Name of the current exchange
        """
        return constants.EXCHANGE_NAME

    async def _track_single_book(self, trading_pair: str):
        """
        Update an order book with changes from the latest batch of received messages
        """
        past_diffs_window: Deque[BitmartOrderBookMessage] = deque()
        self._past_diffs_windows[trading_pair] = past_diffs_window

        message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
        order_book: BitmartOrderBook = self._order_books[trading_pair]

        while True:
            try:
                message: BitmartOrderBookMessage = None
                saved_messages: Deque[BitmartOrderBookMessage] = self._saved_message_queues[trading_pair]
                # Process saved messages first if there are any
                if len(saved_messages) > 0:
                    message = saved_messages.popleft()
                else:
                    message = await message_queue.get()

                if message.type is OrderBookMessageType.SNAPSHOT:
                    past_diffs: List[BitmartOrderBookMessage] = list(past_diffs_window)
                    # only replay diffs later than snapshot, first update active order with snapshot then replay diffs
                    replay_position = bisect.bisect_right(past_diffs, message)
                    replay_diffs = past_diffs[replay_position:]
                    s_bids, s_asks = bitmart_utils.convert_snapshot_message_to_order_book_row(message)
                    order_book.apply_snapshot(s_bids, s_asks, message.update_id)
                    for diff_message in replay_diffs:
                        d_bids, d_asks = bitmart_utils.convert_diff_message_to_order_book_row(diff_message)
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
