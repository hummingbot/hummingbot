#!/usr/bin/env python

import asyncio
import aiohttp
import logging
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional
)
import time
import ujson
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.bitstamp.bitstamp_order_book import BitstampOrderBook
from hummingbot.connector.exchange.bitstamp.bitstamp_utils import (
    convert_to_exchange_trading_pair,
    convert_from_exchange_trading_pair
)

BITSTAMP_ROOT_URL = "https://www.bitstamp.net/api/v2/"
ORDER_BOOK_SNAPSHOT_URL = "order_book/"
TICKER_URL = "ticker/"
TRADING_PAIRS_URL = "trading-pairs-info/"
STREAM_URL = "wss://ws.bitstamp.net"
MAX_RETRIES = 20
NaN = float("nan")


class BitstampAPIOrderBookDataSource(OrderBookTrackerDataSource):
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _bstpobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bstpobds_logger is None:
            cls._bstpobds_logger = logging.getLogger(__name__)
        return cls._bstpobds_logger

    def __init__(self, trading_pairs: Optional[List[str]] = None):
        super().__init__(trading_pairs)

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        tasks = [cls.get_last_traded_price(t_pair) for t_pair in trading_pairs]
        results = await safe_gather(*tasks)
        return {t_pair: result for t_pair, result in zip(trading_pairs, results)}

    @classmethod
    async def get_last_traded_price(cls, trading_pair: str) -> float:
        async with aiohttp.ClientSession() as client:
            resp = await client.get(
                f"{BITSTAMP_ROOT_URL}{TICKER_URL}{convert_to_exchange_trading_pair(trading_pair)}/")
            resp_json = await resp.json()
            return float(resp_json["last"])

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str) -> Dict[str, Any]:
        order_book_url: str = f"{BITSTAMP_ROOT_URL}{ORDER_BOOK_SNAPSHOT_URL}" \
                              f"{convert_to_exchange_trading_pair(trading_pair)}/"
        print(order_book_url)
        async with client.get(order_book_url) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching Bitstamp market snapshot for {trading_pair}. "
                              f"HTTP status is {response.status}.")
            data: Dict[str, Any] = await response.json()
            data = {"trading_pair": trading_pair, **data}

            # Need to add the symbol into the snapshot message for the Kafka message queue.
            # Because otherwise, there'd be no way for the receiver to know which market the
            # snapshot belongs to.

            return data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        async with aiohttp.ClientSession() as client:
            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
            snapshot_timestamp: float = time.time()
            snapshot_msg: OrderBookMessage = BitstampOrderBook.snapshot_message_from_exchange(
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
                trading_pairs: List[str] = self._trading_pairs
                async with websockets.connect(STREAM_URL) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for pair in trading_pairs:
                        subscribe_msg: Dict[str, Any] = {
                            "event": "bts:subscribe",
                            "data": {"channel": f"live_trades_{convert_to_exchange_trading_pair(pair)}"}
                        }
                        await ws.send(ujson.dumps(subscribe_msg))
                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        msg_type: str = msg.get("event", None)
                        if msg_type is None:
                            raise ValueError(f"Bitstamp Websocket message does not contain an event type - {msg}")
                        elif msg_type == "bts:subscription_succeeded":
                            pass
                        elif msg_type == "trade":
                            trade_msg: OrderBookMessage = BitstampOrderBook.trade_message_from_exchange(
                                msg["data"],
                                metadata={"trading_pair": convert_from_exchange_trading_pair(msg["channel"]
                                                                                             .split("_")[2])}
                            )
                            output.put_nowait(trade_msg)
                        else:
                            raise ValueError(
                                f"Bitstamp Websocket received event type other then trade in trade listener - {msg}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = self._trading_pairs
                async with websockets.connect(STREAM_URL) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for pair in trading_pairs:
                        subscribe_msg: Dict[str, Any] = {
                            "event": "bts:subscribe",
                            "data": {"channel": f"diff_order_book_{convert_to_exchange_trading_pair(pair)}"}
                        }
                        await ws.send(ujson.dumps(subscribe_msg))
                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        msg_type: str = msg.get("event", None)
                        if msg_type is None:
                            raise ValueError(f"Bitstamp Websocket message does not contain an event type - {msg}")
                        elif msg_type == "bts:subscription_succeeded":
                            pass
                        elif msg_type == "data":
                            order_book_message: OrderBookMessage = BitstampOrderBook.diff_message_from_exchange(
                                msg["data"],
                                time.time(),
                                metadata={"trading_pair": convert_from_exchange_trading_pair(msg["channel"]
                                                                                             .split("_")[2])}
                            )
                            output.put_nowait(order_book_message)
                        else:
                            raise ValueError(
                                f"Bitstamp Websocket received event type other then data in order book diff listener - "
                                f"{msg}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = self._trading_pairs
                async with websockets.connect(STREAM_URL) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for pair in trading_pairs:
                        subscribe_msg: Dict[str, Any] = {
                            "event": "bts:subscribe",
                            "data": {"channel": f"order_book_{convert_to_exchange_trading_pair(pair)}"}
                        }
                        await ws.send(ujson.dumps(subscribe_msg))
                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        msg_type: str = msg.get("event", None)
                        if msg_type is None:
                            raise ValueError(f"Bitstamp Websocket message does not contain an event type - {msg}")
                        elif msg_type == "bts:subscription_succeeded":
                            pass
                        elif msg_type == "data":
                            order_book_message: OrderBookMessage = BitstampOrderBook.snapshot_message_from_exchange(
                                msg["data"],
                                time.time(),
                                metadata={"trading_pair": convert_from_exchange_trading_pair(msg["channel"]
                                                                                             .split("_")[2])}
                            )
                            output.put_nowait(order_book_message)
                        else:
                            raise ValueError(
                                f"Bitstamp Websocket received event type other then trade in trade listener - {msg}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)
