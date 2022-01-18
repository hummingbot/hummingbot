#!/usr/bin/env python

import asyncio
import logging
import time
from typing import (
    List,
    Optional
)

from hummingbot.connector.exchange.huobi.huobi_api_order_book_data_source import HuobiAPIOrderBookDataSource
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType
)
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger


class HuobiOrderBookTracker(OrderBookTracker):
    _hobt_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._hobt_logger is None:
            cls._hobt_logger = logging.getLogger(__name__)
        return cls._hobt_logger

    def __init__(self,
                 trading_pairs: Optional[List[str]] = None,
                 api_factory: Optional[WebAssistantsFactory] = None):
        super().__init__(data_source=HuobiAPIOrderBookDataSource(trading_pairs=trading_pairs,
                                                                 api_factory=api_factory),
                         trading_pairs=trading_pairs)
        self._order_book_diff_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()
        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._order_book_stream_listener_task: Optional[asyncio.Task] = None

    @property
    def exchange_name(self) -> str:
        return "huobi"

    @property
    def data_source(self) -> OrderBookTrackerDataSource:
        if not self._data_source:
            self._data_source = HuobiAPIOrderBookDataSource(trading_pairs=self._trading_pairs)
        return self._data_source

    @data_source.setter
    def data_source(self, data_source):
        self._data_source = data_source

    def start(self):
        super().start()
        self._order_book_stream_listener_task = safe_ensure_future(
            self._data_source.listen_for_subscriptions()
        )

    def stop(self):
        self._order_book_stream_listener_task and self._order_book_stream_listener_task.cancel()
        super().stop()

    async def _track_single_book(self, trading_pair: str):
        message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
        order_book: OrderBook = self._order_books[trading_pair]
        last_message_timestamp: float = time.time()
        diff_messages_accepted: int = 0

        while True:
            try:
                message: OrderBookMessage = await message_queue.get()
                if message.type is OrderBookMessageType.DIFF:
                    # Huobi websocket messages contain the entire order book state so they should be treated as snapshots
                    order_book.apply_snapshot(message.bids, message.asks, message.update_id)
                    diff_messages_accepted += 1

                    # Output some statistics periodically.
                    now: float = time.time()
                    if int(now / 60.0) > int(last_message_timestamp / 60.0):
                        self.logger().debug(f"Processed {diff_messages_accepted} order book diffs for {trading_pair}.")
                        diff_messages_accepted = 0
                    last_message_timestamp = now
                elif message.type is OrderBookMessageType.SNAPSHOT:
                    order_book.apply_snapshot(message.bids, message.asks, message.update_id)
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
