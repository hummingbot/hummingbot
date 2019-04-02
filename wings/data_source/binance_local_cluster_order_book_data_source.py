#!/usr/bin/env python
import aiohttp
from aiokafka import (
    AIOKafkaConsumer,
    TopicPartition,
    ConsumerRecord
)
import asyncio
import logging
import pandas as pd
import re

from typing import (
    Dict,
    Optional,
    List
)
import conf
from wings.data_source.local_cluster_order_book_data_source import LocalClusterOrderBookDataSource
from wings.model.sql_connection_manager import SQLConnectionManager
from wings.order_book import OrderBook
from wings.orderbook.binance_order_book import BinanceOrderBook


TRADING_PAIR_FILTER = re.compile(r"(BTC|ETH|USDT)$")


class BinanceLocalClusterOrderBookDataSource(LocalClusterOrderBookDataSource):
    DIFF_TOPIC_NAME: str = "binance-market-depth.serialized"
    SNAPSHOT_TOPIC_NAME: str = "binance-market-depth.snapshot"

    _blcobds_logger: Optional[logging.Logger] = None

    @classmethod
    def logger(cls) -> logging.Logger:
        if cls._blcobds_logger is None:
            cls._blcobds_logger = logging.getLogger(__name__)
        return cls._blcobds_logger

    def __init__(self, sql: SQLConnectionManager):
        super().__init__(sql)

    @classmethod
    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        async with aiohttp.ClientSession() as client:
            async with client.get("https://api.binance.com/api/v1/ticker/24hr") as response:
                response: aiohttp.ClientResponse = response
                if response.status != 200:
                    raise IOError(f"Error fetching active Binance markets. HTTP status is {response.status}.")
                data = await response.json()
                all_markets: pd.DataFrame = pd.DataFrame.from_records(data=data, index="symbol")
                filtered_markets: pd.DataFrame = all_markets[
                    [TRADING_PAIR_FILTER.search(i) is not None for i in all_markets.index]].copy()
                btc_price: float = float(all_markets.loc["BTCUSDT"].lastPrice)
                eth_price: float = float(all_markets.loc["ETHUSDT"].lastPrice)
                usd_volume: float = [
                    (
                        quoteVolume * btc_price if symbol.endswith("BTC") else
                        quoteVolume * eth_price if symbol.endswith("ETH") else
                        quoteVolume
                    )
                    for symbol, quoteVolume in zip(filtered_markets.index,
                                                   filtered_markets.quoteVolume.astype("float"))]
                filtered_markets["USDVolume"] = usd_volume
                return filtered_markets.sort_values("USDVolume", ascending=False)

    def get_snapshot_message_query(self, symbol: str) -> str:
        return f"SELECT `timestamp` as `timestamp`, `json` " \
               f"FROM `Binance_{symbol}_Snapshot` " \
               f"ORDER BY `timestamp` DESC LIMIT 1"

    def get_diff_message_query(self, symbol: str) -> str:
        return f"SELECT `timestamp` as `timestamp`, `json` " \
               f"FROM `Binance_{symbol}` " \
               f"WHERE `timestamp` > :timestamp " \
               f"ORDER BY `timestamp`"

    @property
    def order_book_class(self) -> BinanceOrderBook:
        return BinanceOrderBook

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listens to real-time order book diff messages from Binance.
        """
        while True:
            try:
                consumer: AIOKafkaConsumer = AIOKafkaConsumer(self.DIFF_TOPIC_NAME,
                                                              loop=ev_loop,
                                                              bootstrap_servers=conf.kafka_bootstrap_server)
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
        Listens to real-time order book snapshot messages from Binance.
        """
        while True:
            try:
                consumer: AIOKafkaConsumer = AIOKafkaConsumer(self.SNAPSHOT_TOPIC_NAME,
                                                              loop=ev_loop,
                                                              bootstrap_servers=conf.kafka_bootstrap_server)
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

