#!/usr/bin/env python

import asyncio
import logging
import time
from typing import (
    AsyncIterable,
    Dict,
    Optional,
    List,
)
import ujson
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.connector.exchange.fmfw.fmfw_auth import FmfwAuth
from hummingbot.logger import HummingbotLogger
# from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.connector.exchange.fmfw.fmfw_order_book import FmfwOrderBook

FMFW_API_ENDPOINT = "https://api.fmfw.io/api/3"
FMFW_USER_STREAM_ENDPOINT = "wss://api.fmfw.io/api/3/ws/public"
MAX_RETRIES = 20
NaN = float("nan")

Fmfw_PRIVATE_TOPICS = [
    "/spotMarket/tradeOrders",
    "/account/balance",
]


class FmfwAPIUserStreamDataSource(UserStreamTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _cbpausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._cbpausds_logger is None:
            cls._cbpausds_logger = logging.getLogger(__name__)
        return cls._cbpausds_logger

    def __init__(self, fmfw_auth: FmfwAuth, trading_pairs: Optional[List[str]] = []):
        self._fmfw_auth: FmfwAuth = fmfw_auth
        self._trading_pairs = trading_pairs
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._last_recv_time: float = 0
        super().__init__()

    @property
    def order_book_class(self):
        """
        *required
        Get relevant order book class to access class specific methods
        :returns: OrderBook class
        """
        return FmfwOrderBook

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """
        while True:
            try:
                async with websockets.connect(FMFW_USER_STREAM_ENDPOINT) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    subscribe_request: Dict[str, any] = {
                        "method": "subscribe",
                        "ch": "orderbook/full",
                        "params": {
                            "symbols": ["ETHBTC", "MAHAUSDT"]
                        },
                        "id": 123
                    }
                    await ws.send(ujson.dumps(subscribe_request))
                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        output.put_nowait(msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with Coinbase Pro WebSocket connection. "
                                    "Retrying after 30 seconds...", exc_info=True)
                await asyncio.sleep(30.0)

    async def _inner_messages(self,
                              ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        """
        Generator function that returns messages from the web socket stream
        :param ws: current web socket connection
        :returns: message in AsyncIterable format
        """
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                    self._last_recv_time = time.time()
                    yield msg
                except asyncio.TimeoutError:
                    pong_waiter = await ws.ping()
                    self._last_recv_time = time.time()
                    await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await ws.close()
