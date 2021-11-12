#!/usr/bin/env python

import asyncio
import aiohttp
import logging
import time

from typing import (
    AsyncIterable,
    Optional
)
import hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_constants as CONSTANTS

from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_auth import DydxPerpetualAuth
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_order_book import DydxPerpetualOrderBook
from hummingbot.logger import HummingbotLogger


class DydxPerpetualUserStreamDataSource(UserStreamTrackerDataSource):

    HEARTBEAT_INTERVAL = 30.0  # seconds

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, dydx_auth: DydxPerpetualAuth, shared_client: Optional[aiohttp.ClientSession] = None):
        self._dydx_auth: DydxPerpetualAuth = dydx_auth
        self._shared_client: Optional[aiohttp.ClientSession] = shared_client
        self._last_recv_time: float = 0
        super().__init__()
        self._ws = None

    @property
    def order_book_class(self):
        return DydxPerpetualOrderBook

    @property
    def last_recv_time(self):
        return self._last_recv_time

    def _get_shared_client(self) -> aiohttp.ClientSession:
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _create_websocket_connection(self) -> aiohttp.ClientWebSocketResponse:
        """
        Initialize WebSocket client for UserStreamDataSource
        """
        try:
            self.logger().info(f"Connecting to {CONSTANTS.DYDX_WS_URL}")
            return await self._get_shared_client().ws_connect(url=CONSTANTS.DYDX_WS_URL,
                                                              heartbeat=self.HEARTBEAT_INTERVAL,
                                                              autoping=False)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(f"Unexpected error occured when connecting to WebSocket server. Error: {e}")
            raise

    async def _iter_messages(self,
                             ws: aiohttp.ClientWebSocketResponse) -> AsyncIterable[aiohttp.WSMessage]:
        """
        Generator function that returns messages from the web socket stream
        :param ws: current web socket connection
        :returns: message in AsyncIterable format
        """
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                msg: aiohttp.WSMessage = await ws.receive()
                self._last_recv_time = time.time()
                yield msg
        except Exception as e:
            self.logger().network(f"Unexpected error occurred when parsing websocket payload. "
                                  f"Error: {e}")
            raise
        finally:
            await ws.close()

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                self._ws = await self._create_websocket_connection()
                auth_params = self._dydx_auth.get_ws_auth_params()
                await self._ws.send_json(auth_params)
                self.logger().info("Authenticated user stream...")
                async for raw_msg in self._iter_messages(self._ws):
                    if raw_msg.type == aiohttp.WSMsgType.PING:
                        self.logger().debug("Received PING frame. Sending PONG frame...")
                        await self._ws.pong()
                        continue
                    if raw_msg.type == aiohttp.WSMsgType.PONG:
                        self.logger().debug("Received PONG frame.")
                        continue
                    msg = raw_msg.json()
                    if msg.get("type", "") in ["subscribed", "channel_data"]:
                        output.put_nowait(msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with dydx WebSocket connection. "
                                    "Retrying after 30 seconds...", exc_info=True)
            finally:
                # Make sure no background tasks is leaked
                self._ws and await self._ws.close()
                self._last_recv_time = -1
                await self._sleep(30.0)
