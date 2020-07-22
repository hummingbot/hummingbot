#!/usr/bin/env python

import asyncio
from collections import deque, defaultdict
import logging
import time
from typing import (
    Deque,
    Dict,
    List,
    Optional
)
import aiohttp

from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_tracker import (
    OrderBookTracker,
    OrderBookTrackerDataSourceType)
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.remote_api_order_book_data_source import RemoteAPIOrderBookDataSource
from hummingbot.market.kraken.kraken_api_order_book_data_source import KrakenAPIOrderBookDataSource
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.utils.async_utils import safe_gather

KRAKEN_PRICE_URL = "https://api.kraken.com/0/public/Ticker?pair="


class KrakenOrderBookTracker(OrderBookTracker):
    _krobt_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._krobt_logger is None:
            cls._krobt_logger = logging.getLogger(__name__)
        return cls._krobt_logger

    def __init__(self,
                 data_source_type: OrderBookTrackerDataSourceType = OrderBookTrackerDataSourceType.EXCHANGE_API,
                 trading_pairs: Optional[List[str]] = None):
        super().__init__(data_source_type=data_source_type)

        self._order_book_diff_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()

        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._data_source: Optional[OrderBookTrackerDataSource] = None
        self._saved_message_queues: Dict[str, Deque[OrderBookMessage]] = defaultdict(lambda: deque(maxlen=1000))
        self._trading_pairs: Optional[List[str]] = trading_pairs

    @property
    def data_source(self) -> OrderBookTrackerDataSource:
        if not self._data_source:
            if self._data_source_type is OrderBookTrackerDataSourceType.REMOTE_API:
                self._data_source = RemoteAPIOrderBookDataSource()
            elif self._data_source_type is OrderBookTrackerDataSourceType.EXCHANGE_API:
                self._data_source = KrakenAPIOrderBookDataSource(trading_pairs=self._trading_pairs)
            else:
                raise ValueError(f"data_source_type {self._data_source_type} is not supported.")
        return self._data_source

    @property
    def exchange_name(self) -> str:
        return "kraken"

    async def _order_book_diff_router(self):
        """
        Route the real-time order book diff messages to the correct order book.
        """
        last_message_timestamp: float = time.time()
        messages_accepted: int = 0
        messages_rejected: int = 0

        while True:
            try:
                ob_message: OrderBookMessage = await self._order_book_diff_stream.get()
                trading_pair: str = ob_message.trading_pair

                if trading_pair not in self._tracking_message_queues:
                    messages_rejected += 1
                    continue
                message_queue: asyncio.Queue = self._tracking_message_queues[trading_pair]
                # Check the order book's initial update ID. If it's larger, don't bother.
                order_book: OrderBook = self._order_books[trading_pair]

                if order_book.snapshot_uid > ob_message.update_id:
                    messages_rejected += 1
                    continue
                await message_queue.put(ob_message)
                messages_accepted += 1

                # Log some statistics.
                now: float = time.time()
                if int(now / 60.0) > int(last_message_timestamp / 60.0):
                    self.logger().debug("Diff messages processed: %d, rejected: %d",
                                        messages_accepted,
                                        messages_rejected)
                    messages_accepted = 0
                    messages_rejected = 0

                last_message_timestamp = now
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unknown error. Retrying after 5 seconds.", exc_info=True)
                await asyncio.sleep(5.0)

    async def _update_last_trade_prices_loop(self):
        while True:
            try:
                if len(self._trading_pairs) == len(self._order_books):
                    tasks = [self._update_last_trade_price(t_pair) for t_pair in self._trading_pairs]
                    await safe_gather(*tasks)
                    await asyncio.sleep(10)
                else:
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching last trade price.", exc_info=True)
                await asyncio.sleep(30)

    async def _update_last_trade_price(self, trading_pair: str):
        order_book: OrderBook = self._order_books.get(trading_pair, None)
        async with aiohttp.ClientSession() as client:
            resp = await client.get(KRAKEN_PRICE_URL + trading_pair)
            resp_json = await resp.json()
            record = list(resp_json["result"].values())[0]
            # print(f"{trading_pair} {resp_json}")
            order_book.last_trade_price = float(record["c"][0])
