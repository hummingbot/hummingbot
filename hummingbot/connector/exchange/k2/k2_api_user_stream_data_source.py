#!/usr/bin/env python
import asyncio
import logging
import time
import ujson
import websockets

from typing import (
    Any,
    AsyncIterable,
    Dict,
    Optional,
    List
)

import hummingbot.connector.exchange.k2.k2_constants as constants

from hummingbot.connector.exchange.k2.k2_auth import K2Auth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger


class K2APIUserStreamDataSource(UserStreamTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, auth: K2Auth, trading_pairs: Optional[List[str]] = []):
        self._websocket_client: websockets.WebSocketClientProtocol = None
        self._k2_auth: K2Auth = auth
        self._trading_pairs = trading_pairs

        self._listen_for_user_stream_tasks = None

        self._last_recv_time: float = 0
        super().__init__()

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def _init_websocket_connection(self):
        """
        Initialize WebSocket client for UserStreamDataSource
        """
        try:
            if self._websocket_client is None:
                self._websocket_client = await websockets.connect(constants.WSS_URL)
        except Exception:
            self.logger().network("Unexpected error occured with K2 WebSocket Connection")

    async def _authenticate(self, ws: websockets.WebSocketClientProtocol):
        """
        Authenticates user to Websocket.
        """
        while True:
            try:

                auth_payload = await self._k2_auth.get_ws_auth_payload()
                await ws.send(ujson.dumps(auth_payload))
                resp = await ws.recv()

                msg: Dict[str, Any] = ujson.loads(resp)
                if msg["success"] is not True:
                    raise
                else:
                    return

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected Error occur authenticating for to websocket channel. Retrying in 5 seconds,",
                                    exc_info=True)
                raise

    async def _subscribe_to_channels(self, ws: websockets.WebSocketClientProtocol):
        """
        Subscribe to SubscribeMyOrders, SubscribeMyTrades and SubscribeMyBalanceChanges channels
        """
        for channel in ["SubscribeMyOrders", "SubscribeMyTrades", "SubscribeMyBalanceChanges"]:
            params: Dict[str, Any] = {
                "name": channel,
                "data": ""
            }
            await ws.send(ujson.dumps(params))
            resp = await ws.recv()

            msg: Dict[str, Any] = ujson.loads(resp)
            if msg["success"] is not True:
                raise

    async def _inner_messages(self, ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        """
        Iterates through each message received from the websocket. Also updates self._last_recv_time
        """
        try:
            while True:
                msg: str = await ws.recv()
                self._last_recv_time = time.time()
                yield msg
        except websockets.exceptions.ConnectionClosed:
            return
        finally:
            await ws.close()

    async def listen_for_user_stream(self, ev_loop, output: asyncio.Queue) -> AsyncIterable[Any]:
        """
        Subscribe to user stream via websocket, and keep the connection open for incoming messages
        """
        while True:
            try:
                self._websocket_client = await websockets.connect(constants.WSS_URL)
                await self._authenticate(self._websocket_client)
                self.logger().info("Authenticated to WebSocket connection. ")
                await self._subscribe_to_channels(self._websocket_client)
                self.logger().info("Subscribed to all Private WebSocket streams. ")
                async for msg in self._inner_messages(self._websocket_client):
                    output.put_nowait(ujson.loads(msg))
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error occured with K2 WebSocket Connection. Retrying in 5 seconds.",
                    exc_info=True
                )
                if self._websocket_client is not None:
                    await self._websocket_client.close()
                    self._websocket_client = None
                await asyncio.sleep(5.0)
