#!/usr/bin/env python
from abc import abstractmethod

import asyncio
import logging
import pandas as pd
import re

from sqlalchemy.exc import DatabaseError
from sqlalchemy.sql import text
from sqlalchemy.sql.elements import TextClause
import time
from typing import (
    Dict,
    Optional
)

from hummingbot.logger import HummingbotLogger
import wings
from wings.model.sql_connection_manager import SQLConnectionManager
from wings.order_book import OrderBook
from wings.order_book_message import OrderBookMessage
from wings.data_source.order_book_tracker_data_source import OrderBookTrackerDataSource
from wings.order_book_tracker_entry import OrderBookTrackerEntry

TRADING_PAIR_FILTER = re.compile(r"(BTC|ETH|USDT)$")


class LocalClusterOrderBookDataSource(OrderBookTrackerDataSource):
    _lcobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._lcobds_logger is None:
            cls._lcobds_logger = logging.getLogger(__name__)
        return cls._lcobds_logger

    def __init__(self, sql: SQLConnectionManager):
        super().__init__()
        self._sql: SQLConnectionManager = sql

    @classmethod
    @abstractmethod
    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        raise NotImplementedError

    @property
    @abstractmethod
    def order_book_class(self) -> OrderBook:
        raise NotImplementedError

    @abstractmethod
    def get_diff_message_query(self, symbol: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_snapshot_message_query(self, symbol: str) -> str:
        raise NotImplementedError

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        # Get the currently active markets
        sql: SQLConnectionManager = self._sql
        active_markets: pd.DataFrame = await self.get_active_exchange_markets()

        # Get the latest order book snapshots from database
        now: float = time.time()
        yesterday: float = now - 86400.0
        retval: Dict[str, OrderBookTrackerEntry] = {}
        ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()

        with sql.engine.connect() as conn:
            for symbol in active_markets.index:
                symbol: str = symbol
                stmt: TextClause = text(self.get_snapshot_message_query(symbol))
                try:
                    row = await ev_loop.run_in_executor(wings.get_executor(), lambda: conn.execute(stmt).fetchone())
                except DatabaseError:
                    self.logger().warning("Cannot find last snapshot for %s, skipping.", symbol, exc_info=True)
                    continue
                if row is None:
                    continue

                snapshot_msg: OrderBookMessage = self.order_book_class.snapshot_message_from_db(row)

                snapshot_timestamp: float = row[0]
                if snapshot_timestamp > yesterday:
                    order_book: OrderBook = self.order_book_class.from_snapshot(snapshot_msg)
                    retval[symbol] = OrderBookTrackerEntry(symbol, snapshot_timestamp, order_book)
                    stmt: TextClause = text(self.get_diff_message_query(symbol))
                    try:
                        rows = await ev_loop.run_in_executor(
                            wings.get_executor(),
                            lambda: conn.execute(stmt, timestamp=(snapshot_timestamp-60)*1e3).fetchall()
                        )
                        for row in rows:
                            diff_msg: OrderBookMessage = self.order_book_class.diff_message_from_db(row)
                            if diff_msg.update_id > order_book.snapshot_uid:
                                order_book.apply_diffs(diff_msg.bids, diff_msg.asks, diff_msg.update_id)
                    except DatabaseError:
                        continue
                    finally:
                        self.logger().debug("Fetched order book snapshot for %s.", symbol)
        return retval

    @abstractmethod
    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listens to real-time order book diff messages.
        """
        raise NotImplementedError

    @abstractmethod
    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listens to real-time order book snapshot messages.
        """
        raise NotImplementedError
