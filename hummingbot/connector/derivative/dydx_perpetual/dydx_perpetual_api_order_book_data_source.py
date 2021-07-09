#!/usr/bin/env python

import asyncio
from decimal import Decimal

import aiohttp
import logging
# import pandas as pd
# import math

import requests
import cachetools.func

from typing import AsyncIterable, Dict, List, Optional, Any

import time
import ujson
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_order_book import DydxPerpetualOrderBook
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_row import ClientOrderBookRow


MARKETS_URL = "/markets"
TICKER_URL = "/stats"
SNAPSHOT_URL = "/orderbook/"

WS_URL = "wss://api.dydx.exchange/v3/ws"
DYDX_V3_API_URL = "https://api.dydx.exchange/v3"


class DydxPerpetualAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    __daobds__logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.__daobds__logger is None:
            cls.__daobds__logger = logging.getLogger(__name__)
        return cls.__daobds__logger

    def __init__(self, trading_pairs: List[str] = None, rest_api_url="", websocket_url="", token_configuration=None):
        super().__init__(trading_pairs)
        self.REST_URL = rest_api_url
        self.WS_URL = websocket_url
        self._get_tracking_pair_done_event: asyncio.Event = asyncio.Event()
        self.order_book_create_function = lambda: OrderBook()

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        async with aiohttp.ClientSession() as client:
            retval = {}
            for pair in trading_pairs:
                resp = await client.get(f"{DYDX_V3_API_URL}{TICKER_URL}/{pair}")
                resp_json = await resp.json()
                retval[pair] = float(resp_json["markets"][pair]["close"])
            return retval

    @property
    def order_book_class(self) -> DydxPerpetualOrderBook:
        return DydxPerpetualOrderBook

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    async def get_snapshot(self, client: aiohttp.ClientSession, trading_pair: str, level: int = 0) -> Dict[str, any]:
        async with client.get(f"{DYDX_V3_API_URL}{SNAPSHOT_URL}/{trading_pair}") as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(
                    f"Error fetching dydx market snapshot for {trading_pair}. " f"HTTP status is {response.status}."
                )
            data: Dict[str, Any] = await response.json()
            data["trading_pair"] = trading_pair
            return data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        async with aiohttp.ClientSession() as client:
            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair, 1000)
            snapshot_timestamp: float = time.time()
            snapshot_msg: OrderBookMessage = DydxPerpetualOrderBook.snapshot_message_from_exchange(
                snapshot,
                snapshot_timestamp,
                metadata={"id": trading_pair, "rest": True}
            )
            order_book: OrderBook = self.order_book_create_function()
            bids = [ClientOrderBookRow(Decimal(bid["price"]), Decimal(bid["amount"]), snapshot_msg.update_id) for bid in snapshot_msg.bids]
            asks = [ClientOrderBookRow(Decimal(ask["price"]), Decimal(ask["amount"]), snapshot_msg.update_id) for ask in snapshot_msg.asks]
            order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
            return order_book

    async def _inner_messages(self, ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
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

    @staticmethod
    @cachetools.func.ttl_cache(ttl=10)
    def get_mid_price(trading_pair: str) -> Optional[Decimal]:
        resp = requests.get(url=f"{DYDX_V3_API_URL}{TICKER_URL}/{trading_pair}")
        record = resp.json()
        data = record["markets"][trading_pair]
        mid_price = (Decimal(data['high']) + Decimal(data['low'])) / 2

        return mid_price

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        try:
            async with aiohttp.ClientSession() as client:
                async with client.get(f"{DYDX_V3_API_URL}{MARKETS_URL}", timeout=5) as response:
                    if response.status == 200:
                        all_trading_pairs: Dict[str, Any] = await response.json()
                        valid_trading_pairs: list = []
                        for key, val in all_trading_pairs["markets"].items():
                            if val['status'] == "ONLINE":
                                valid_trading_pairs.append(key)
                        return valid_trading_pairs
        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for dydx trading pairs
            pass

        return []

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                async with websockets.connect(f"{WS_URL}") as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for pair in self._trading_pairs:
                        subscribe_request: Dict[str, Any] = {
                            "type": "subscribe",
                            "channel": "v3_trades",
                            "id": pair
                        }
                        await ws.send(ujson.dumps(subscribe_request))
                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        if "contents" in msg:
                            if "trades" in msg["contents"]:
                                if msg["type"] == "channel_data":
                                    for datum in msg["contents"]["trades"]:
                                        msg["ts"] = time.time()
                                        trade_msg: OrderBookMessage = DydxPerpetualOrderBook.trade_message_from_exchange(datum, msg)
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
                async with websockets.connect(f"{WS_URL}") as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for pair in self._trading_pairs:
                        subscribe_request: Dict[str, Any] = {
                            "type": "subscribe",
                            "channel": "v3_orderbook",
                            "id": pair
                        }
                        await ws.send(ujson.dumps(subscribe_request))
                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        if "contents" in msg:
                            msg["trading_pair"] = msg["id"]
                            if msg["type"] == "channel_data":
                                ts = time.time()
                                order_msg: OrderBookMessage = DydxPerpetualOrderBook.diff_message_from_exchange(msg["contents"], ts, msg)
                                output.put_nowait(order_msg)
                            elif msg["type"] == "subscribed":
                                msg["rest"] = False
                                ts = time.time()
                                order_msg: OrderBookMessage = DydxPerpetualOrderBook.snapshot_message_from_exchange(msg["contents"], ts, msg)
                                output.put_nowait(order_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        pass
