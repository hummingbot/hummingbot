#!/usr/bin/env python

import aiohttp
import asyncio
import json
import logging
import pandas as pd
import time
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional,
    Set
)
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.duedex.duedex_order_book import DuedexOrderBook
from hummingbot.connector.exchange.duedex.duedex_utils import convert_to_exchange_trading_pair, string_timestamp_to_seconds

DUEDEX_WS_URI = "wss://feed.duedex.com/v1/feed"
DUEDEX_TICKER_URL = "https://api.duedex.com/v1/ticker"


class DuedexAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _orderbook_source_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._orderbook_source_logger is None:
            cls._orderbook_source_logger = logging.getLogger(__name__)
        return cls._orderbook_source_logger

    def __init__(self, trading_pairs: List[str]):
        super().__init__(trading_pairs)

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        results = dict()
        async with aiohttp.ClientSession() as client:
            resp = await client.get(DUEDEX_TICKER_URL)
            resp_json = await resp.json()
            for trading_pair in trading_pairs:
                resp_record = [o for o in resp_json["data"] if o["instrument"] == convert_to_exchange_trading_pair(trading_pair)][0]
                results[trading_pair] = float(resp_record["lastPrice"])
        return results

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str) -> Dict[str, Any]:
        # Duedex currently does not provide rest query depth, but uses query ticker instead.
        url = DUEDEX_TICKER_URL + '/' + convert_to_exchange_trading_pair(trading_pair)
        async with client.get(url) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching DueDEX market snapshot for {trading_pair}. "
                              f"HTTP status is {response.status}.")
            api_data = json.loads(await response.read())
            if api_data["code"] != 0:
                raise IOError(f"Error fetching DueDEX market snapshot for {trading_pair}. "
                              f"Error code is {api_data['code']}.")
            data: Dict[str, Any] = {"bids": [[api_data["data"]["bestBid"], 1]],
                                    "asks": [[api_data["data"]["bestAsk"], 1]]
                                    }
            return data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        async with aiohttp.ClientSession() as client:
            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
            snapshot_msg: OrderBookMessage = DuedexOrderBook.snapshot_message_from_exchange(
                snapshot,
                timestamp=time.time(),
                metadata={"instrument": convert_to_exchange_trading_pair(trading_pair), "sequence": 0}
            )
            order_book: OrderBook = self.order_book_create_function()
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
                    pong_waiter = await ws.ping()
                    await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
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
                async with websockets.connect(DUEDEX_WS_URI) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    subscribe_request: Dict[str, Any] = {
                        "type": "subscribe",
                        "channels": [
                            {
                                "name": "matches",
                                "instruments": [convert_to_exchange_trading_pair(trading_pair) for trading_pair in trading_pairs],
                            }
                        ]
                    }
                    await ws.send(json.dumps(subscribe_request))
                    async for raw_msg in self._inner_messages(ws):
                        msg: Dict[str, Any] = json.loads(raw_msg)
                        if "type" in msg:
                            if msg["type"] == "subscriptions":
                                for channel in msg["channels"]:
                                    self.logger().debug(f"Success to subscribe {channel}")
                            elif msg["type"] in ["snapshot", "update"]:
                                if msg["channel"] == "matches":
                                    for match in msg["data"]:
                                        trade_message: OrderBookMessage = DuedexOrderBook.trade_message_from_exchange(
                                            match, string_timestamp_to_seconds(match['timestamp']),
                                            metadata={"instrument": msg["instrument"], "sequence": msg["sequence"]}
                                        )
                                        output.put_nowait(trade_message)
                                else:
                                    self.logger().debug(f"Unrecognized channel received from Duedex websocket: {channel}")
                            else:
                                self.logger().debug(f"Unrecognized type received from Duedex websocket: {msg['type']}")
                        else:
                            self.logger().debug(f"Unrecognized message received from Duedex websocket: {msg}")
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
                async with websockets.connect(DUEDEX_WS_URI) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    subscribe_request: Dict[str, Any] = {
                        "type": "subscribe",
                        "channels": [
                            {
                                "name": "level2",
                                "instruments": [convert_to_exchange_trading_pair(trading_pair) for trading_pair in trading_pairs],
                            }
                        ]
                    }
                    await ws.send(json.dumps(subscribe_request))
                    async for raw_msg in self._inner_messages(ws):
                        msg: Dict[str, Any] = json.loads(raw_msg)
                        if "type" in msg:
                            if msg["type"] == "subscriptions":
                                for channel in msg["channels"]:
                                    self.logger().debug(f"Success to subscribe {channel['name']}")
                            elif msg["type"] == "update" and msg["channel"] == "level2":
                                order_book_message: OrderBookMessage = DuedexOrderBook.diff_message_from_exchange(
                                    msg["data"], string_timestamp_to_seconds(msg['timestamp']),
                                    metadata={"instrument": msg["instrument"], "sequence": msg["sequence"]}
                                )
                                output.put_nowait(order_book_message)
                            elif msg["type"] == "snapshot" and msg["channel"] == "level2":
                                snapshot_message: OrderBookMessage = DuedexOrderBook.snapshot_message_from_exchange(
                                    msg["data"], string_timestamp_to_seconds(msg['timestamp']),
                                    metadata={"instrument": msg["instrument"], "sequence": msg["sequence"]})
                                output.put_nowait(snapshot_message)
                                self.logger().info(f"Saved order book snapshot for {msg['instrument']} at listen_for_order_book_diffs.")
                            else:
                                self.logger().warning(f"Unrecognized message received from Duedex websocket: {msg}")
                        else:
                            self.logger().warning(f"Unrecognized message received from Duedex websocket: {msg}")
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
                received_snapshot_trading_pairs: Set[str] = set()
                async with websockets.connect(DUEDEX_WS_URI) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    subscribe_request: Dict[str, Any] = {
                        "type": "subscribe",
                        "channels": [
                            {
                                "name": "level2",
                                "instruments": [convert_to_exchange_trading_pair(trading_pair) for trading_pair in trading_pairs],
                            }
                        ]
                    }
                    await ws.send(json.dumps(subscribe_request))
                    async for raw_msg in self._inner_messages(ws):
                        msg: Dict[str, Any] = json.loads(raw_msg)
                        if "type" in msg:
                            if msg["type"] == "subscriptions":
                                for channel in msg["channels"]:
                                    self.logger().debug(f"Success to subscribe {channel['name']}")
                            elif msg["type"] == "snapshot" and msg["channel"] == "level2":
                                snapshot_message: OrderBookMessage = DuedexOrderBook.snapshot_message_from_exchange(
                                    msg["data"], string_timestamp_to_seconds(msg['timestamp']),
                                    metadata={"instrument": msg["instrument"], "sequence": msg["sequence"]})
                                output.put_nowait(snapshot_message)
                                self.logger().debug(f"Saved order book snapshot for {msg['instrument']}")
                                received_snapshot_trading_pairs.add(msg["instrument"])
                                if len(received_snapshot_trading_pairs) == len(trading_pairs):
                                    break  # Exit this websocket to receive messages after received all.
                            elif msg["type"] == "update" and msg["channel"] == "level2":
                                pass
                            else:
                                self.logger().debug(f"Unrecognized message received from Duedex websocket: {msg}")
                        else:
                            self.logger().debug(f"Unrecognized message received from Duedex websocket: {msg}")
                    this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                    next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                    delta: float = next_hour.timestamp() - time.time()
                    await asyncio.sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await asyncio.sleep(5.0)
