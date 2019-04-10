#!/usr/bin/env python
import re
import time

import aiohttp
from aiokafka import (
    AIOKafkaConsumer,
    TopicPartition,
    ConsumerRecord
)
import asyncio
import logging
import pandas as pd

from typing import (
    Dict,
    Optional,
    List
)

from sqlalchemy import text
from sqlalchemy.exc import (
    ProgrammingError,
    DatabaseError
)
from sqlalchemy.sql.elements import TextClause
import conf
import wings
from wings.data_source.local_cluster_order_book_data_source import LocalClusterOrderBookDataSource
from wings.model.sql_connection_manager import SQLConnectionManager
from wings.order_book_message import (
    OrderBookMessage,
    DDEXOrderBookMessage
)
from wings.order_book_tracker_entry import (
    RadarRelayOrderBookTrackerEntry
)
from wings.orderbook.radar_relay_order_book import RadarRelayOrderBook
from wings.tracker.radar_relay_active_order_tracker import RadarRelayActiveOrderTracker

TRADING_PAIR_FILTER = re.compile(r"(TUSD|ETH|DAI)$")


class RadarRelayLocalClusterOrderBookDataSource(LocalClusterOrderBookDataSource):
    DIFF_TOPIC_NAME: str = "radarrelay-order.serialized"
    SNAPSHOT_TOPIC_NAME: str = "radarrelay-market-depth.snapshot"

    _hlcobds_logger: Optional[logging.Logger] = None

    @classmethod
    def logger(cls) -> logging.Logger:
        if cls._hlcobds_logger is None:
            cls._hlcobds_logger = logging.getLogger(__name__)
        return cls._hlcobds_logger

    def __init__(self, sql: SQLConnectionManager):
        super().__init__(sql)

    @classmethod
    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        """
        Returns all currently active WETH, DAI trading pairs from RadarRelay, sorted by volume in descending order.
        """
        async with aiohttp.ClientSession() as client:
            async with client.get("https://api.radarrelay.com/v2/markets?include=ticker,stats") as response:
                response: aiohttp.ClientResponse = response
                if response.status != 200:
                    raise IOError(f"Error fetching active Radar Relay markets. HTTP status is {response.status}.")
                data = await response.json()
                all_markets: pd.DataFrame = pd.DataFrame.from_records(data=data, index="id")
                fetch_markets: pd.DataFrame = all_markets[
                    lambda df: [FETCH_MARKET_SYMBOL_PATTERN.search(i) is not None for i in df.index]
                ]

                weth_dai_price: float = float(fetch_markets.loc["WETH-DAI"]["ticker"]["price"])
                dai_volume: List[float] = []
                for row in fetch_markets.itertuples():
                    product_name: str = row.Index
                    base_volume: float = float(row.stats["volume24Hour"])
                    if product_name.endswith("WETH"):
                        dai_volume.append(weth_dai_price * base_volume)
                    else:
                        dai_volume.append(base_volume)
                fetch_markets.loc[:, "DAIVolume"] = dai_volume

                return fetch_markets.sort_values("DAIVolume", ascending=False)

    def get_snapshot_message_query(self, symbol: str) -> str:
        return f"SELECT `timestamp` as `timestamp`, `json` " \
               f"FROM `radarrelay_{symbol}_Snapshot` " \
               f"ORDER BY `timestamp` DESC LIMIT 1"

    def get_diff_message_query(self, symbol: str) -> str:
        return f"SELECT `timestamp` as `ts`, `json` " \
               f"FROM `radarrelay_{symbol}` " \
               f"WHERE `timestamp` > :timestamp " \
               f"ORDER BY `timestamp`"

    @property
    def order_book_class(self) -> RadarRelayOrderBook:
        return RadarRelayOrderBook

    async def get_tracking_pairs(self) -> Dict[str, RadarRelayOrderBookTrackerEntry]:
        # Get the currently active markets
        sql: SQLConnectionManager = self._sql
        active_markets: pd.DataFrame = await self.get_active_exchange_markets()

        # Get the latest order book snapshots from database
        now: float = time.time()
        yesterday: float = now - 86400.0
        retval: Dict[str, RadarRelayOrderBookTrackerEntry] = {}
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

                snapshot_timestamp: float = row[0]
                if snapshot_timestamp > yesterday:
                    snapshot_timestamp: float = time.time()
                    snapshot_msg: DDEXOrderBookMessage = self.order_book_class.snapshot_message_from_db(
                        row,
                        {"marketId": symbol}
                    )

                    order_book: RadarRelayOrderBook = RadarRelayOrderBook()
                    radar_relay_active_order_tracker: RadarRelayActiveOrderTracker = RadarRelayActiveOrderTracker()
                    bids, asks = radar_relay_active_order_tracker.convert_snapshot_message_to_order_book_row(
                        snapshot_msg)
                    order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)

                    retval[symbol] = RadarRelayOrderBookTrackerEntry(
                        symbol,
                        snapshot_timestamp,
                        order_book,
                        radar_relay_active_order_tracker
                    )

                    stmt: TextClause = text(self.get_diff_message_query(symbol))
                    try:
                        rows = await ev_loop.run_in_executor(
                            wings.get_executor(),
                            lambda: conn.execute(stmt, timestamp=(snapshot_timestamp-60)*1e3).fetchall()
                        )
                        for row in rows:
                            diff_msg: OrderBookMessage = self.order_book_class.diff_message_from_db(row)
                            if diff_msg.update_id > order_book.snapshot_uid:
                                bids, asks = retval[symbol].active_order_tracker.\
                                    convert_diff_message_to_order_book_row(diff_msg)
                                order_book.apply_diffs(bids, asks, diff_msg.update_id)
                    except DatabaseError:
                        continue
                    except ProgrammingError:
                        continue
                    finally:
                        self.logger().debug("Fetched order book snapshot for %s.", symbol)
        return retval

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listens to real-time order book diff messages from Radar Relay.
        """
        while True:
            try:
                consumer: AIOKafkaConsumer = AIOKafkaConsumer(self.DIFF_TOPIC_NAME,
                                                              loop=ev_loop,
                                                              bootstrap_servers=conf.kafka_2["bootstrap_servers"])
                await consumer.start()
                partition: TopicPartition = list(consumer.assignment())[0]
                await consumer.seek_to_end(partition)

                while True:
                    response: Dict[TopicPartition, List[ConsumerRecord]] = await consumer.getmany(partition,
                                                                                                  timeout_ms=1000)
                    if partition in response:
                        for record in response[partition]:
                            output.put_nowait(self.order_book_class.diff_message_from_kafka(record))
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unknown error. Retrying after 5 seconds.", exc_info=True)
                await asyncio.sleep(5.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listens to real-time order book snapshot messages from Radar Relay.
        """
        while True:
            try:
                consumer: AIOKafkaConsumer = AIOKafkaConsumer(self.SNAPSHOT_TOPIC_NAME,
                                                              loop=ev_loop,
                                                              bootstrap_servers=conf.kafka_2["bootstrap_servers"])
                await consumer.start()
                partition: TopicPartition = list(consumer.assignment())[0]
                await consumer.seek_to_end(partition)

                while True:
                    response: Dict[TopicPartition, List[ConsumerRecord]] = await consumer.getmany(partition,
                                                                                                  timeout_ms=1000)
                    if partition in response:
                        for record in response[partition]:
                            output.put_nowait(self.order_book_class.snapshot_message_from_kafka(record))
            except asyncio.CancelledError:
                raise
            except:
                self.logger().error("Unknown error. Retrying after 5 seconds.", exc_info=True)
                await asyncio.sleep(5.0)

