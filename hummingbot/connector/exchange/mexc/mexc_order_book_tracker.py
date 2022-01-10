#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import asyncio
import logging
import time
from typing import (
    List,
    Optional
)

import aiohttp
from hummingbot.core.data_type.order_book import OrderBook

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType
)

from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.mexc.mexc_api_order_book_data_source import MexcAPIOrderBookDataSource


class MexcOrderBookTracker(OrderBookTracker):
    _mexcobt_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._mexcobt_logger is None:
            cls._mexcobt_logger = logging.getLogger(__name__)
        return cls._mexcobt_logger

    def __init__(self,
                 trading_pairs: Optional[List[str]] = None,
                 shared_client: Optional[aiohttp.ClientSession] = None,
                 throttler: Optional[AsyncThrottler] = None,):
        super().__init__(MexcAPIOrderBookDataSource(trading_pairs, shared_client=shared_client, throttler=throttler), trading_pairs)
        self._order_book_diff_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()
        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._order_book_stream_listener_task: Optional[asyncio.Task] = None

    @property
    def exchange_name(self) -> str:
        return "mexc"

    def start(self):
        super().start()
        self._order_book_stream_listener_task = safe_ensure_future(self._data_source.listen_for_subscriptions())

    def stop(self):
        if self._order_book_stream_listener_task:
            self._order_book_stream_listener_task.cancel()
        super().stop()

    async def _order_book_diff_router(self):
        last_message_timestamp: float = time.time()
        messages_queued: int = 0
        messages_accepted: int = 0
        messages_rejected: int = 0

        while True:
            try:
                ob_message: OrderBookMessage = await self._order_book_diff_stream.get()
                trading_pair: str = ob_message.trading_pair

                if trading_pair not in self._tracking_message_queues:
                    continue
                message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
                order_book: OrderBook = self._order_books[trading_pair]

                if order_book.snapshot_uid > ob_message.update_id:
                    messages_rejected += 1
                    continue
                await message_queue.put(ob_message)
                messages_accepted += 1

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
            except Exception as ex:
                self.logger().network(
                    "Unexpected error routing order book messages." + repr(ex),
                    exc_info=True,
                    app_warning_msg="Unexpected error routing order book messages. Retrying after 5 seconds."
                )
                await asyncio.sleep(5.0)

    async def _track_single_book(self, trading_pair: str):
        message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
        order_book: OrderBook = self._order_books[trading_pair]
        last_message_timestamp: float = time.time()
        diff_messages_accepted: int = 0

        while True:
            try:
                message: OrderBookMessage = await message_queue.get()
                if message.type is OrderBookMessageType.DIFF:
                    order_book.apply_diffs(message.bids, message.asks, message.update_id)
                    diff_messages_accepted += 1

                    now: float = time.time()
                    if int(now / 60.0) > int(last_message_timestamp / 60):
                        self.logger().debug(f"Processed {diff_messages_accepted} order book diffs for {trading_pair}.")
                        diff_messages_accepted = 0
                    last_message_timestamp = now
                elif message.type is OrderBookMessageType.SNAPSHOT:
                    order_book.apply_snapshot(message.bids, message.asks, message.update_id)
                    self.logger().debug(f"Processed order book snapshot for {trading_pair}.")
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().network(
                    f"Unexpected error tracking order book for {trading_pair}." + repr(ex),
                    exc_info=True,
                    app_warning_msg="Unexpected error tracking order book. Retrying after 5 seconds."
                )
                await asyncio.sleep(5.0)
