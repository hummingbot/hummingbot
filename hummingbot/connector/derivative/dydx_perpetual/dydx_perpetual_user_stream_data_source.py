#!/usr/bin/env python

import asyncio
import aiohttp
import logging
import time
from typing import (
    AsyncIterable,
    Optional
)
import ujson
import websockets
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_auth import DydxPerpetualAuth
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_api_order_book_data_source import DydxPerpetualAPIOrderBookDataSource
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_order_book import DydxPerpetualOrderBook

DYDX_WS_URL = "wss://api.dydx.exchange/v3/ws"

DYDX_ROOT_API = "https://api.dydx.exchange/v3"


class DydxPerpetualUserStreamDataSource(UserStreamTrackerDataSource):

    _krausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._krausds_logger is None:
            cls._krausds_logger = logging.getLogger(__name__)
        return cls._krausds_logger

    def __init__(self, orderbook_tracker_data_source: DydxPerpetualAPIOrderBookDataSource, dydx_auth: DydxPerpetualAuth):
        self._dydx_auth: DydxPerpetualAuth = dydx_auth
        self._orderbook_tracker_data_source: DydxPerpetualAPIOrderBookDataSource = orderbook_tracker_data_source
        self._shared_client: Optional[aiohttp.ClientSession] = None
        self._last_recv_time: float = 0
        super().__init__()

    @property
    def order_book_class(self):
        return DydxPerpetualOrderBook

    @property
    def last_recv_time(self):
        return self._last_recv_time

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                async with websockets.connect(f"{DYDX_WS_URL}") as ws:
                    ws: websockets.WebSocketClientProtocol = ws

                    auth_params = self._dydx_auth.get_ws_auth_params()

                    await ws.send(ujson.dumps(auth_params))

                    async for raw_msg in self._inner_messages(ws):
                        self._last_recv_time = time.time()

                        diff_msg = ujson.loads(raw_msg)
                        if diff_msg['type'] in ['subscribed', 'channel_data']:
                            output.put_nowait(diff_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with dydx WebSocket connection. "
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
                msg: str = await asyncio.wait_for(ws.recv(), timeout=None)    # This will throw the ConnectionClosed exception on disconnect
                if msg == "ping":
                    await ws.send("pong")  # skip returning this and handle this protocol level message here
                else:
                    yield msg
        except websockets.exceptions.ConnectionClosed:
            self.logger().warning("dydx websocket connection closed. Reconnecting...")
            return
        finally:
            await ws.close()

    async def stop(self):
        if self._shared_client is not None and not self._shared_client.closed:
            await self._shared_client.close()
