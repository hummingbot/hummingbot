#!/usr/bin/env python

import time
import asyncio
import logging
import ujson
import websockets
import hummingbot.connector.exchange.bitmart.bitmart_constants as CONSTANTS

from typing import Optional, List, AsyncIterable, Any, Dict
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.bitmart.bitmart_auth import BitmartAuth
from hummingbot.connector.exchange.bitmart import bitmart_utils
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class BitmartAPIUserStreamDataSource(UserStreamTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 10.0
    PING_TIMEOUT = 10.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        return throttler

    def __init__(
        self,
        bitmart_auth: BitmartAuth,
        throttler: Optional[AsyncThrottler] = None,
        trading_pairs: Optional[List[str]] = None,
    ):
        super().__init__()
        self._bitmart_auth: BitmartAuth = bitmart_auth
        self._trading_pairs = trading_pairs or []
        self._websocket_client: websockets.WebSocketClientProtocol = None
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._last_recv_time: float = 0
        self._throttler = throttler or self._get_throttler_instance()

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def _init_websocket_connection(self) -> websockets.WebSocketClientProtocol:
        """
        Initialize WebSocket client for UserStreamDataSource
        """
        try:
            if self._websocket_client is None:
                self._websocket_client = await websockets.connect(CONSTANTS.WSS_URL)
            return self._websocket_client
        except Exception:
            self.logger().network("Unexpected error occured with BitMart WebSocket Connection")
            raise

    async def _authenticate(self, ws: websockets.WebSocketClientProtocol):
        """
        Authenticates user to websocket
        """
        try:
            auth_payload: Dict[str, Any] = self._bitmart_auth.get_ws_auth_payload(bitmart_utils.get_ms_timestamp())
            await ws.send(ujson.dumps(auth_payload, escape_forward_slashes=False))
            auth_resp = await ws.recv()
            auth_resp: Dict[str, Any] = ujson.loads(auth_resp)

            if "errorCode" in auth_resp:
                self.logger().error(f"WebSocket login errored with message: {auth_resp['errorMessage']}",
                                    exc_info=True)
                raise ConnectionError
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Error occurred when authenticating to user stream.", exc_info=True)
            raise

    async def _subscribe_to_channels(self, ws: websockets.WebSocketClientProtocol):
        """
        Subscribes to Private User Channels
        """
        try:
            # BitMart WebSocket API currently offers only spot/user/order private channel.
            for trading_pair in self._trading_pairs:
                params: Dict[str, Any] = {
                    "op": "subscribe",
                    "args": [f"spot/user/order:{bitmart_utils.convert_to_exchange_trading_pair(trading_pair)}"]
                }
                await ws.send(ujson.dumps(params))

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Error occured during subscribing to Bitmart private channels.", exc_info=True)
            raise

    async def _inner_messages(self,
                              ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                    msg = bitmart_utils.decompress_ws_message(msg)
                    self._last_recv_time = time.time()
                    yield msg
                except asyncio.TimeoutError:
                    await asyncio.wait_for(ws.ping(), timeout=self.PING_TIMEOUT)
                    self._last_recv_time = time.time()
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except websockets.exceptions.ConnectionClosed:
            return
        finally:
            await ws.close()

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
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
                    try:
                        msg = ujson.loads(msg)
                        if msg is None:
                            continue
                        output.put_nowait(msg)
                    except Exception:
                        self.logger().error(
                            "Unexpected error when parsing BitMart user_stream message. ", exc_info=True
                        )
                        raise
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error with BitMart WebSocket connection. Retrying after 30 seconds...",
                    exc_info=True
                )
                if self._websocket_client is not None:
                    await self._websocket_client.close()
                    self._websocket_client = None
                await asyncio.sleep(30.0)
