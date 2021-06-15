#!/usr/bin/env python

import asyncio
import aiohttp
import base64
import logging
import pandas as pd
from typing import (
    Dict,
    Optional,
    Tuple,
    AsyncIterable
)
import pickle
import time
import websockets
from websockets.exceptions import ConnectionClosed

import conf
from hummingbot.connector.exchange.binance.binance_order_book import BinanceOrderBook
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry


class RemoteAPIOrderBookDataSource(OrderBookTrackerDataSource):
    SNAPSHOT_REST_URL = "https://api.coinalpha.com/order_book_tracker/snapshot"
    SNAPSHOT_STREAM_URL = "wss://api.coinalpha.com/ws/order_book_tracker/snapshot_stream"
    DIFF_STREAM_URL = "wss://api.coinalpha.com/ws/order_book_tracker/diff_stream"

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _raobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._raobds_logger is None:
            cls._raobds_logger = logging.getLogger(__name__)
        return cls._raobds_logger

    def __init__(self):
        super().__init__()
        self._client_session: Optional[aiohttp.ClientSession] = None

    @property
    def authentication_headers(self) -> Dict[str, str]:
        auth_str: str = f"{conf.coinalpha_order_book_api_username}:{conf.coinalpha_order_book_api_password}"
        encoded_auth: str = base64.standard_b64encode(auth_str.encode("utf8")).decode("utf8")
        return {
            "Authorization": f"Basic {encoded_auth}"
        }

    async def get_client_session(self) -> aiohttp.ClientSession:
        if self._client_session is None:
            self._client_session = aiohttp.ClientSession()
        return self._client_session

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        auth: aiohttp.BasicAuth = aiohttp.BasicAuth(login=conf.coinalpha_order_book_api_username,
                                                    password=conf.coinalpha_order_book_api_password)
        client_session: aiohttp.ClientSession = await self.get_client_session()
        response: aiohttp.ClientResponse = await client_session.get(self.SNAPSHOT_REST_URL, auth=auth)
        timestamp: float = time.time()
        if response.status != 200:
            raise EnvironmentError(f"Error fetching order book tracker snapshot from {self.SNAPSHOT_REST_URL}.")

        binary_data: bytes = await response.read()
        order_book_tracker_data: Dict[str, Tuple[pd.DataFrame, pd.DataFrame]] = pickle.loads(binary_data)
        retval: Dict[str, OrderBookTrackerEntry] = {}

        for trading_pair, (bids_df, asks_df) in order_book_tracker_data.items():
            order_book: BinanceOrderBook = BinanceOrderBook()
            order_book.apply_numpy_snapshot(bids_df.values, asks_df.values)
            retval[trading_pair] = OrderBookTrackerEntry(trading_pair, timestamp, order_book)

        return retval

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

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                async with websockets.connect(self.DIFF_STREAM_URL,
                                              extra_headers=self.authentication_headers) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    async for msg in self._inner_messages(ws):
                        output.put_nowait(msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                async with websockets.connect(self.SNAPSHOT_STREAM_URL,
                                              extra_headers=self.authentication_headers) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    async for msg in self._inner_messages(ws):
                        output.put_nowait(msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30.0)
