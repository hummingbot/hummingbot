#!/usr/bin/env python

import aiohttp
import asyncio
import gzip
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
)
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.huobi.huobi_order_book import HuobiOrderBook
from hummingbot.connector.exchange.huobi.huobi_utils import convert_to_exchange_trading_pair

HUOBI_SYMBOLS_URL = "https://api.huobi.pro/v1/common/symbols"
HUOBI_TICKER_URL = "https://api.huobi.pro/market/tickers"
HUOBI_DEPTH_URL = "https://api.huobi.pro/market/depth"
HUOBI_WS_URI = "wss://api.huobi.pro/ws"


class HuobiAPIOrderBookDataSource(OrderBookTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _haobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._haobds_logger is None:
            cls._haobds_logger = logging.getLogger(__name__)
        return cls._haobds_logger

    def __init__(self, trading_pairs: List[str]):
        super().__init__(trading_pairs)

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        results = dict()
        async with aiohttp.ClientSession() as client:
            resp = await client.get(HUOBI_TICKER_URL)
            resp_json = await resp.json()
            for trading_pair in trading_pairs:
                resp_record = [o for o in resp_json["data"] if o["symbol"] == convert_to_exchange_trading_pair(trading_pair)][0]
                results[trading_pair] = float(resp_record["close"])
        return results

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        try:
            from hummingbot.connector.exchange.huobi.huobi_utils import convert_from_exchange_trading_pair

            async with aiohttp.ClientSession() as client:
                async with client.get(HUOBI_SYMBOLS_URL, timeout=10) as response:
                    if response.status == 200:
                        all_trading_pairs: Dict[str, Any] = await response.json()
                        valid_trading_pairs: list = []
                        for item in all_trading_pairs["data"]:
                            if item["state"] == "online":
                                valid_trading_pairs.append(item["symbol"])
                        trading_pair_list: List[str] = []
                        for raw_trading_pair in valid_trading_pairs:
                            converted_trading_pair: Optional[str] = \
                                convert_from_exchange_trading_pair(raw_trading_pair)
                            if converted_trading_pair is not None:
                                trading_pair_list.append(converted_trading_pair)
                        return trading_pair_list

        except Exception:
            # Do nothing if the request fails -- there will be no autocomplete for huobi trading pairs
            pass

        return []

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str) -> Dict[str, Any]:
        # when type is set to "step0", the default value of "depth" is 150
        params: Dict = {"symbol": convert_to_exchange_trading_pair(trading_pair), "type": "step0"}
        async with client.get(HUOBI_DEPTH_URL, params=params) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching Huobi market snapshot for {trading_pair}. "
                              f"HTTP status is {response.status}.")
            api_data = await response.read()
            data: Dict[str, Any] = json.loads(api_data)
            return data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        async with aiohttp.ClientSession() as client:
            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
            snapshot_msg: OrderBookMessage = HuobiOrderBook.snapshot_message_from_exchange(
                snapshot,
                metadata={"trading_pair": trading_pair}
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
                async with websockets.connect(HUOBI_WS_URI) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for trading_pair in trading_pairs:
                        subscribe_request: Dict[str, Any] = {
                            "sub": f"market.{convert_to_exchange_trading_pair(trading_pair)}.trade.detail",
                            "id": convert_to_exchange_trading_pair(trading_pair)
                        }
                        await ws.send(json.dumps(subscribe_request))

                    async for raw_msg in self._inner_messages(ws):
                        # Huobi compresses their ws data
                        encoded_msg: bytes = gzip.decompress(raw_msg)
                        # Huobi's data value for id is a large int too big for ujson to parse
                        msg: Dict[str, Any] = json.loads(encoded_msg.decode('utf-8'))
                        if "ping" in msg:
                            await ws.send(f'{{"op":"pong","ts": {str(msg["ping"])}}}')
                        elif "subbed" in msg:
                            pass
                        elif "ch" in msg:
                            trading_pair = msg["ch"].split(".")[1]
                            for data in msg["tick"]["data"]:
                                trade_message: OrderBookMessage = HuobiOrderBook.trade_message_from_exchange(
                                    data, metadata={"trading_pair": trading_pair}
                                )
                                output.put_nowait(trade_message)
                        else:
                            self.logger().debug(f"Unrecognized message received from Huobi websocket: {msg}")
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
                async with websockets.connect(HUOBI_WS_URI) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for trading_pair in trading_pairs:
                        subscribe_request: Dict[str, Any] = {
                            "sub": f"market.{convert_to_exchange_trading_pair(trading_pair)}.depth.step0",
                            "id": convert_to_exchange_trading_pair(trading_pair)
                        }
                        await ws.send(json.dumps(subscribe_request))

                    async for raw_msg in self._inner_messages(ws):
                        # Huobi compresses their ws data
                        encoded_msg: bytes = gzip.decompress(raw_msg)
                        # Huobi's data value for id is a large int too big for ujson to parse
                        msg: Dict[str, Any] = json.loads(encoded_msg.decode('utf-8'))
                        if "ping" in msg:
                            await ws.send(f'{{"op":"pong","ts": {str(msg["ping"])}}}')
                        elif "subbed" in msg:
                            pass
                        elif "ch" in msg:
                            order_book_message: OrderBookMessage = HuobiOrderBook.diff_message_from_exchange(msg)
                            output.put_nowait(order_book_message)
                        else:
                            self.logger().debug(f"Unrecognized message received from Huobi websocket: {msg}")
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
                async with aiohttp.ClientSession() as client:
                    for trading_pair in trading_pairs:
                        try:
                            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
                            snapshot_message: OrderBookMessage = HuobiOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                metadata={"trading_pair": trading_pair}
                            )
                            output.put_nowait(snapshot_message)
                            self.logger().debug(f"Saved order book snapshot for {trading_pair}")
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
