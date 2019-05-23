#!/usr/bin/env python
import asyncio
import logging
from typing import (
    Optional)

from hummingbot.logger import HummingbotLogger
from wings.model.sql_connection_manager import SQLConnectionManager
from wings.order_book_tracker import (
    OrderBookTracker,
    OrderBookTrackerDataSourceType
)
from hummingbot.market.bittrex.bittrex_local_cluster_order_book_data_source import BittrexLocalClusterOrderBookDataSource

from hummingbot.market.data_source.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.market.data_source.remote_api_order_book_data_source import RemoteAPIOrderBookDataSource
import conf


class BittrexOrderBookTracker(OrderBookTracker):
    _btobt_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._btobt_logger is None:
            cls._btobt_logger = logging.getLogger(__name__)
        return cls._btobt_logger

    def __init__(self,
                 data_source_type: OrderBookTrackerDataSourceType = OrderBookTrackerDataSourceType.LOCAL_CLUSTER):
        super().__init__(data_source_type=data_source_type)
        self._order_book_diff_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()
        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._data_source: Optional[OrderBookTrackerDataSource] = None

    @property
    def data_source(self) -> OrderBookTrackerDataSource:
        if not self._data_source:
            if self._data_source_type is OrderBookTrackerDataSourceType.LOCAL_CLUSTER:
                self._data_source = BittrexLocalClusterOrderBookDataSource(
                    SQLConnectionManager.get_order_books_instance(db_conf=conf.order_books_db_2))
            elif self._data_source_type is OrderBookTrackerDataSourceType.REMOTE_API:
                self._data_source = RemoteAPIOrderBookDataSource()
            else:
                raise ValueError(f"data_source_type {self._data_source_type} is not supported.")
        return self._data_source

    @property
    async def exchange_name(self) -> str:
        return "bittrex"

    async def start(self):
        self._order_book_diff_listener_task = asyncio.ensure_future(
            self.data_source.listen_for_order_book_diffs(self._ev_loop, self._order_book_diff_stream)
        )
        self._order_book_snapshot_listener_task = asyncio.ensure_future(
            self.data_source.listen_for_order_book_snapshots(self._ev_loop, self._order_book_snapshot_stream)
        )
        self._refresh_tracking_task = asyncio.ensure_future(
            self._refresh_tracking_loop()
        )
        self._order_book_diff_router_task = asyncio.ensure_future(
            self._order_book_diff_router()
        )
        self._order_book_snapshot_router_task = asyncio.ensure_future(
            self._order_book_snapshot_router()
        )

        await asyncio.gather(self._order_book_snapshot_listener_task,
                             self._order_book_diff_listener_task,
                             self._order_book_snapshot_router_task,
                             self._order_book_diff_router_task,
                             self._refresh_tracking_task)
