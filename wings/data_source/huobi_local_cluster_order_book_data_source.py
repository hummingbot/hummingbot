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
from wings.orderbook.huobi_order_book import HuobiOrderBook

TRADING_PAIR_FILTER = re.compile(r"(btc|eth|usdt)$")


class HuobiLocalClusterOrderBookDataSource(LocalClusterOrderBookDataSource):
    DIFF_TOPIC_NAME: str = "huobi-market-depth.serialized"
    SNAPSHOT_TOPIC_NAME: str = "huobi-market-depth.snapshot"

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
        async with aiohttp.ClientSession() as client:
            async with client.get(f"https://api.huobipro.com/market/tickers") as response:
                response: aiohttp.ClientResponse = response
                if response.status != 200:
                    raise IOError(f"Error fetching active huobi markets. "
                                  f"HTTP status is {response.status}.")
                data = await response.json()
                all_markets: pd.DataFrame = pd.DataFrame.from_records(data=data['data'], index="symbol")

                filtered_markets: pd.DataFrame = all_markets[
                    [TRADING_PAIR_FILTER.search(i) is not None for i in all_markets.index]].copy()
                btc_price: float = float(all_markets.loc["btcusdt"].close)
                eth_price: float = float(all_markets.loc["ethusdt"].close)
                usd_volume: float = [
                    (
                        quoteVolume * btc_price if symbol.endswith("btc") else
                        quoteVolume * eth_price if symbol.endswith("eth") else
                        quoteVolume
                    )
                    for symbol, quoteVolume in zip(filtered_markets.index,
                                                   filtered_markets.vol.astype("float"))]
                filtered_markets["USDVolume"] = usd_volume
                return filtered_markets.sort_values("USDVolume", ascending=False)

    def get_snapshot_message_query(self, symbol: str) -> str:
        return f"SELECT `timestamp` as `timestamp`, `json` " \
               f"FROM `huobi_{symbol}_Snapshot` " \
               f"ORDER BY `timestamp` DESC LIMIT 1"

    def get_diff_message_query(self, symbol: str) -> str:
        return f"SELECT `timestamp` as `ts`, `json` " \
               f"FROM `huobi_{symbol}` " \
               f"WHERE `timestamp` > :timestamp " \
               f"ORDER BY `timestamp`"

    @property
    def order_book_class(self) -> HuobiOrderBook:
        return HuobiOrderBook

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

