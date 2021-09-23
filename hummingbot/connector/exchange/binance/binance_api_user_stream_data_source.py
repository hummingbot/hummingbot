#!/usr/bin/env python

import asyncio
import aiohttp
import logging
import time
import ujson
import websockets

import hummingbot.connector.exchange.binance.binance_constants as CONSTANTS

from binance.client import Client as BinanceClient
from typing import (
    AsyncIterable,
    Dict,
    Optional,
    Tuple,
)

from hummingbot.connector.exchange.binance import binance_utils
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger


class BinanceAPIUserStreamDataSource(UserStreamTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0
    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800  # Recommended to Ping/Update listen key to keep connection alive

    _bausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bausds_logger is None:
            cls._bausds_logger = logging.getLogger(__name__)
        return cls._bausds_logger

    def __init__(self, binance_client: Optional[BinanceClient] = None, domain: str = "com", throttler: Optional[AsyncThrottler] = None):
        self._binance_client: BinanceClient = binance_client
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._last_recv_time: float = 0
        self._domain = domain
        self._throttler = throttler or self._get_throttler_instance()

        self._listen_key_initialized_event: asyncio.Event = asyncio.Event()
        self._last_listen_key_ping_ts = 0
        super().__init__()

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        return AsyncThrottler(CONSTANTS.RATE_LIMITS)

    async def get_listen_key(self):
        async with aiohttp.ClientSession() as client:
            async with self._throttler.execute_task(limit_id=CONSTANTS.BINANCE_USER_STREAM_PATH_URL):
                url = binance_utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_PATH_URL, domain=self._domain)
                async with client.post(url=url,
                                       headers={"X-MBX-APIKEY": self._binance_client.API_KEY}) as response:
                    response: aiohttp.ClientResponse = response
                    if response.status != 200:
                        raise IOError(f"Error fetching user stream listen key. Response: {response}")
                    data: Dict[str, str] = await response.json()
                    return data["listenKey"]

    async def ping_listen_key(self, listen_key: str) -> bool:
        async with aiohttp.ClientSession() as client:
            async with self._throttler.execute_task(limit_id=CONSTANTS.BINANCE_USER_STREAM_PATH_URL):
                url = binance_utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_PATH_URL, domain=self._domain)
                async with client.put(url=url,
                                      headers={"X-MBX-APIKEY": self._binance_client.API_KEY},
                                      params={"listenKey": listen_key}) as response:
                    data: Tuple[str, any] = await response.json()
                    if "code" in data:
                        self.logger().warning(f"Failed to refresh the listen key {listen_key}: {data}")
                        return False
                    return True

    async def _iter_messages(self, ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                    self._last_recv_time = time.time()
                    yield msg
                except asyncio.TimeoutError:
                    pong_waiter = await ws.ping()
                    await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
                    self._last_recv_time = time.time()

        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except websockets.exceptions.ConnectionClosed:
            return
        finally:
            await ws.close()

    async def get_ws_connection(self) -> websockets.WebSocketClientProtocol:
        url = CONSTANTS.WSS_URL.format(self._domain)
        stream_url: str = f"{url}/{self._current_listen_key}"
        self.logger().info(f"Reconnecting to {stream_url}.")

        # Create the WS connection.
        ws = await websockets.connect(stream_url)
        return ws

    async def _manage_listen_key_task_loop(self):
        try:
            while True:
                now = int(time.time())
                if self._current_listen_key is None:
                    self._current_listen_key = await self.get_listen_key()
                    self.logger().info(f"Successfully obtained listen key {self._current_listen_key}")
                    self._listen_key_initialized_event.set()
                    self._last_listen_key_ping_ts = int(time.time())

                if now - self._last_listen_key_ping_ts >= self.LISTEN_KEY_KEEP_ALIVE_INTERVAL:
                    success: bool = await self.ping_listen_key()
                    if not success:
                        self.logger().error("Error occurred renewing listen key... ")
                        break
                    else:
                        self.logger().info(f"Refreshed listen key {self._current_listen_key}.")
                        self._last_listen_key_ping_ts = int(time.time())
                else:
                    await asyncio.sleep(self.LISTEN_KEY_KEEP_ALIVE_INTERVAL)
        finally:
            self._current_listen_key = None
            self._listen_key_initialized_event.clear()
            await self._ws.close()
            self._ws = None

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        try:
            while True:
                try:

                    self._manage_listen_key_task = safe_ensure_future(self._manage_listen_key_task_loop())
                    await self._listen_key_initialized_event.wait()

                    self._ws: websockets.WebSocketClientProtocol = await self.get_ws_connection()
                    async for msg in self._iter_messages(self._ws):
                        decoded: Dict[str, any] = ujson.loads(msg)
                        output.put_nowait(decoded)
                except websockets.ConnectionClosed:
                    self.logger().error("Websocket connection closed unexpectedly. Retrying in 5 seconds...",
                                        exc_info=True)
                    await asyncio.sleep(5)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.logger().error(f"Unexpected error while maintaining the user event listen key. Retrying after 5 seconds... "
                                        f"Error: {e}",
                                        exc_info=True)
                    await asyncio.sleep(5)
        finally:
            # Make sure no background task is leaked.
            self._manage_listen_key_task and self._manage_listen_key_task.cancel()
            self._current_listen_key = None
