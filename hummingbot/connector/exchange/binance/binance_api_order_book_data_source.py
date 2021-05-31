#!/usr/bin/env python

import asyncio
import aiohttp
import logging
import pandas as pd
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional
)
from decimal import Decimal
import re
import time
import ujson
import websockets
from websockets.exceptions import ConnectionClosed
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.binance.binance_order_book import BinanceOrderBook
from hummingbot.connector.exchange.binance.binance_utils import convert_to_exchange_trading_pair

TRADING_PAIR_FILTER = re.compile(r"(BTC|ETH|USDT)$")

SNAPSHOT_REST_URL = "https://api.binance.{}/api/v1/depth"
DIFF_STREAM_URL = "wss://stream.binance.{}:9443/ws"
TICKER_PRICE_CHANGE_URL = "https://api.binance.{}/api/v1/ticker/24hr"
EXCHANGE_INFO_URL = "https://api.binance.{}/api/v1/exchangeInfo"


class BinanceAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _baobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._baobds_logger is None:
            cls._baobds_logger = logging.getLogger(__name__)
        return cls._baobds_logger

    def __init__(self, trading_pairs: List[str], domain="com"):
        super().__init__(trading_pairs)
        self._order_book_create_function = lambda: OrderBook()
        self._domain = domain

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str], domain: str = "com") -> Dict[str, float]:
        tasks = [cls.get_last_traded_price(t_pair, domain) for t_pair in trading_pairs]
        results = await safe_gather(*tasks)
        return {t_pair: result for t_pair, result in zip(trading_pairs, results)}

    @classmethod
    async def get_last_traded_price(cls, trading_pair: str, domain: str = "com") -> float:
        async with aiohttp.ClientSession() as client:
            url = TICKER_PRICE_CHANGE_URL.format(domain)
            resp = await client.get(f"{url}?symbol={convert_to_exchange_trading_pair(trading_pair)}")
            resp_json = await resp.json()
            return float(resp_json["lastPrice"])

    @staticmethod
    @async_ttl_cache(ttl=2, maxsize=1)
    async def get_all_mid_prices(domain="com") -> Optional[Decimal]:
        from hummingbot.connector.exchange.binance.binance_utils import convert_from_exchange_trading_pair
        async with aiohttp.ClientSession() as client:
            url = "https://api.binance.{}/api/v3/ticker/bookTicker".format(domain)
            resp = await client.get(url)
            resp_json = await resp.json()
            ret_val = {}
            for record in resp_json:
                pair = convert_from_exchange_trading_pair(record["symbol"])
                ret_val[pair] = (Decimal(record.get("bidPrice", "0")) + Decimal(record.get("askPrice", "0"))) / Decimal("2")
            return ret_val

    @staticmethod
    async def fetch_trading_pairs(domain="com") -> List[str]:
        try:
            from hummingbot.connector.exchange.binance.binance_utils import convert_from_exchange_trading_pair
            async with aiohttp.ClientSession() as client:
                url = EXCHANGE_INFO_URL.format(domain)
                async with client.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        raw_trading_pairs = [d["symbol"] for d in data["symbols"] if d["status"] == "TRADING"]
                        trading_pair_list: List[str] = []
                        for raw_trading_pair in raw_trading_pairs:
                            converted_trading_pair: Optional[str] = \
                                convert_from_exchange_trading_pair(raw_trading_pair)
                            if converted_trading_pair is not None:
                                trading_pair_list.append(converted_trading_pair)
                        return trading_pair_list

        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for binance trading pairs
            pass

        return []

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str, limit: int = 1000,
                           domain: str = "com") -> Dict[str, Any]:
        params: Dict = {"limit": str(limit), "symbol": convert_to_exchange_trading_pair(trading_pair)} if limit != 0 \
            else {"symbol": convert_to_exchange_trading_pair(trading_pair)}
        url = SNAPSHOT_REST_URL.format(domain)
        async with client.get(url, params=params) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching market snapshot for {trading_pair}. "
                              f"HTTP status is {response.status}.")
            data: Dict[str, Any] = await response.json()

            # Need to add the symbol into the snapshot message for the Kafka message queue.
            # Because otherwise, there'd be no way for the receiver to know which market the
            # snapshot belongs to.

            return data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        async with aiohttp.ClientSession() as client:
            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair, 1000, self._domain)
            snapshot_timestamp: float = time.time()
            snapshot_msg: OrderBookMessage = BinanceOrderBook.snapshot_message_from_exchange(
                snapshot,
                snapshot_timestamp,
                metadata={"trading_pair": trading_pair}
            )
            order_book = self.order_book_create_function()
            order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
            return order_book

    async def _inner_messages(self,
                              ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                    yield msg
                except asyncio.TimeoutError:
                    try:
                        pong_waiter = await ws.ping()
                        await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
                    except asyncio.TimeoutError:
                        raise
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await ws.close()

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                ws_path: str = "/".join([f"{convert_to_exchange_trading_pair(trading_pair).lower()}@trade"
                                         for trading_pair in self._trading_pairs])
                url = DIFF_STREAM_URL.format(self._domain)
                stream_url: str = f"{url}/{ws_path}"

                async with websockets.connect(stream_url) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        trade_msg: OrderBookMessage = BinanceOrderBook.trade_message_from_exchange(msg)
                        output.put_nowait(trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                ws_path: str = "/".join([f"{convert_to_exchange_trading_pair(trading_pair).lower()}@depth"
                                         for trading_pair in self._trading_pairs])
                url = DIFF_STREAM_URL.format(self._domain)
                stream_url: str = f"{url}/{ws_path}"

                async with websockets.connect(stream_url) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        order_book_message: OrderBookMessage = BinanceOrderBook.diff_message_from_exchange(
                            msg, time.time())
                        output.put_nowait(order_book_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                async with aiohttp.ClientSession() as client:
                    for trading_pair in self._trading_pairs:
                        try:
                            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair,
                                                                               domain=self._domain)
                            snapshot_timestamp: float = time.time()
                            snapshot_msg: OrderBookMessage = BinanceOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                snapshot_timestamp,
                                metadata={"trading_pair": trading_pair}
                            )
                            output.put_nowait(snapshot_msg)
                            self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                            # Be careful not to go above Binance's API rate limits.
                            await asyncio.sleep(5.0)
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            self.logger().error("Unexpected error.", exc_info=True)
                            await asyncio.sleep(5.0)
                    this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                    next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                    delta: float = next_hour.timestamp() - time.time()
                    await asyncio.sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await asyncio.sleep(5.0)
