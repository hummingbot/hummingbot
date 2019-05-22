#!/usr/bin/env python
import re

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

import conf
from wings.data_source.local_cluster_order_book_data_source import LocalClusterOrderBookDataSource
from wings.model.sql_connection_manager import SQLConnectionManager
from wings.order_book import OrderBook
from wings.orderbook.bittrex_order_book import BittrexOrderBook


class BittrexLocalClusterOrderBookDataSource(LocalClusterOrderBookDataSource):
    DIFF_TOPIC_NAME: str = "bittrex-market-depth.serialized"
    SNAPSHOT_TOPIC_NAME: str = "bittrex-market-depth.snapshot"
    FETCH_MARKET_SYMBOL_PATTERN = re.compile(r"^(BTC|ETH|USDT)-")
    _bthlcobds_logger: Optional[logging.Logger] = None

    @classmethod
    def logger(cls) -> logging.Logger:
        if cls._bthlcobds_logger is None:
            cls._bthlcobds_logger = logging.getLogger(__name__)
        return cls._bthlcobds_logger

    def __init__(self, sql: SQLConnectionManager):
        super().__init__(sql)

    @classmethod
    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        """
        Returns all currently active BTC trading pairs from Bittrex, sorted by volume in descending order.
        """
        async with aiohttp.ClientSession() as client:
            async with client.get("https://bittrex.com/api/v1.1/public/getmarketsummaries") as response:
                response: aiohttp.ClientResponse = response
                if response.status != 200:
                    raise IOError(f"Error fetching active Bittrex markets. HTTP status is {response.status}.")
                data = await response.json()
                all_markets: pd.DataFrame = pd.DataFrame.from_records(data=data["result"], index="MarketName")
                fetch_markets: pd.DataFrame = all_markets[
                    lambda df: [cls.FETCH_MARKET_SYMBOL_PATTERN.search(i) is not None for i in df.index]
                ]
                btc_price: float = fetch_markets.loc["USDT-BTC"].Last
                eth_price: float = fetch_markets.loc["USDT-ETH"].Last
                usdt_volume: List[float] = []
                for row in fetch_markets.itertuples():
                    product_name: str = row.Index
                    base_volume: float = row.BaseVolume
                    if product_name.startswith("BTC"):
                        usdt_volume.append(btc_price * base_volume)
                    elif product_name.startswith("ETH"):
                        usdt_volume.append(eth_price * base_volume)
                    else:
                        usdt_volume.append(base_volume)
                fetch_markets["USDTVolume"] = usdt_volume
                return fetch_markets.sort_values("USDTVolume", ascending=False)

    def get_snapshot_message_query(self, symbol: str) -> str:
        return f"SELECT `timestamp` as `timestamp`, `json` " \
               f"FROM `bittrex_{symbol}_Snapshot` " \
               f"ORDER BY `timestamp` DESC LIMIT 1"

    def get_diff_message_query(self, symbol: str) -> str:
        return f"SELECT `timestamp` as `timestamp`, `json` " \
               f"FROM `bittrex_{symbol}` " \
               f"WHERE `timestamp` > :timestamp " \
               f"ORDER BY `timestamp`"

    @property
    def order_book_class(self) -> OrderBook:
        return BittrexOrderBook

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listens to real-time order book diff messages from Huobi.
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
        Listens to real-time order book snapshot messages from Huobi.
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
