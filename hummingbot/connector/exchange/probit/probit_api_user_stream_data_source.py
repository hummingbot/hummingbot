#!/usr/bin/env python

import asyncio
import logging
import time
import ujson
import websockets

import hummingbot.connector.exchange.probit.probit_constants as CONSTANTS

from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional,
)

from hummingbot.connector.exchange.probit.probit_auth import ProbitAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger


class ProbitAPIUserStreamDataSource(UserStreamTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 probit_auth: ProbitAuth,
                 trading_pairs: Optional[List[str]] = [],
                 domain: str = "com"):
        self._domain: str = domain
        self._websocket_client: websockets.WebSocketClientProtocol = None
        self._probit_auth: ProbitAuth = probit_auth
        self._trading_pairs = trading_pairs

        self._last_recv_time: float = 0
        super().__init__()

    @property
    def exchange_name(self) -> str:
        if self._domain == "com":
            return CONSTANTS.EXCHANGE_NAME
        else:
            return f"{CONSTANTS.EXCHANGE_NAME}_{self._domain}"

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def _init_websocket_connection(self) -> websockets.WebSocketClientProtocol:
        """
        Initialize WebSocket client for UserStreamDataSource
        """
        try:
            if self._websocket_client is None:
                self._websocket_client = await websockets.connect(CONSTANTS.WSS_URL.format(self._domain))
            return self._websocket_client
        except Exception:
            self.logger().network("Unexpected error occured with ProBit WebSocket Connection")

    async def _authenticate(self, ws: websockets.WebSocketClientProtocol):
        """
        Authenticates user to websocket
        """
        try:
            auth_payload: Dict[str, Any] = await self._probit_auth.get_ws_auth_payload()
            await ws.send(ujson.dumps(auth_payload, escape_forward_slashes=False))
            auth_resp = await ws.recv()
            auth_resp: Dict[str, Any] = ujson.loads(auth_resp)

            if auth_resp["result"] != "ok":
                self.logger().error(f"Response: {auth_resp}",
                                    exc_info=True)
                raise
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().info("Error occurred when authenticating to user stream. ",
                               exc_info=True)
            raise

    async def _subscribe_to_channels(self, ws: websockets.WebSocketClientProtocol):
        """
        Subscribes to Private User Channels
        """
        try:
            for channel in CONSTANTS.WS_PRIVATE_CHANNELS:
                sub_payload = {
                    "type": "subscribe",
                    "channel": channel
                }
                await ws.send(ujson.dumps(sub_payload))

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(f"Error occured subscribing to {self.exchange_name} private channels. ",
                                exc_info=True)

    async def _inner_messages(self,
                              ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        try:
            while True:
                msg: str = await ws.recv()
                self._last_recv_time = int(time.time())
                yield msg
        except websockets.exceptions.ConnectionClosed:
            return
        finally:
            await ws.close()

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue) -> AsyncIterable[Any]:
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """

        while True:
            try:
                ws: websockets.WebSocketClientProtocol = await self._init_websocket_connection()
                self.logger().info("Authenticating to User Stream...")
                await self._authenticate(ws)
                self.logger().info("Successfully authenticated to User Stream.")
                await self._subscribe_to_channels(ws)
                self.logger().info("Successfully subscribed to all Private channels.")

                async for msg in self._inner_messages(ws):
                    output.put_nowait(ujson.loads(msg))
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error with Probit WebSocket connection. Retrying after 30 seconds...",
                    exc_info=True
                )
                if self._websocket_client is not None:
                    await self._websocket_client.close()
                    self._websocket_client = None
                await asyncio.sleep(30.0)
