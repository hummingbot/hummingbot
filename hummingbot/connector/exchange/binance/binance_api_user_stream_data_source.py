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

    _bausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bausds_logger is None:
            cls._bausds_logger = logging.getLogger(__name__)
        return cls._bausds_logger

    def __init__(self, binance_client: BinanceClient, domain: str = "com", throttler: Optional[AsyncThrottler] = None):
        self._binance_client: BinanceClient = binance_client
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._last_recv_time: float = 0
        self._domain = domain
        self._throttler = throttler or self._get_throttler_instance()
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
                        raise IOError(f"Error fetching user stream listen key. HTTP status is {response.status}.")
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

    async def _inner_messages(self, ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
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

    async def messages(self) -> AsyncIterable[str]:
        async with (await self.get_ws_connection()) as ws:
            async for msg in self._inner_messages(ws):
                yield msg

    async def get_ws_connection(self) -> websockets.WebSocketClientProtocol:
        url = CONSTANTS.WSS_URL.format(self._domain)
        stream_url: str = f"{url}{self._current_listen_key}"
        self.logger().info(f"Reconnecting to {stream_url}.")

        # Create the WS connection.
        return websockets.connect(stream_url)

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        try:
            while True:
                try:
                    if self._current_listen_key is None:
                        self._current_listen_key = await self.get_listen_key()
                        self.logger().debug(f"Obtained listen key {self._current_listen_key}.")
                        if self._listen_for_user_stream_task is not None:
                            self._listen_for_user_stream_task.cancel()
                        self._listen_for_user_stream_task = safe_ensure_future(self.log_user_stream(output))
                        await self.wait_til_next_tick(seconds=60.0)

                    success: bool = await self.ping_listen_key(self._current_listen_key)
                    if not success:
                        self._current_listen_key = None
                        if self._listen_for_user_stream_task is not None:
                            self._listen_for_user_stream_task.cancel()
                            self._listen_for_user_stream_task = None
                        continue
                    self.logger().debug(f"Refreshed listen key {self._current_listen_key}.")

                    await self.wait_til_next_tick(seconds=60.0)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    self.logger().error("Unexpected error while maintaining the user event listen key. Retrying after "
                                        "5 seconds...", exc_info=True)
                    await asyncio.sleep(5)
        finally:
            # Make sure no background task is leaked.
            if self._listen_for_user_stream_task is not None:
                self._listen_for_user_stream_task.cancel()
                self._listen_for_user_stream_task = None
            self._current_listen_key = None

    async def log_user_stream(self, output: asyncio.Queue):
        while True:
            try:
                async for message in self.messages():
                    decoded: Dict[str, any] = ujson.loads(message)
                    output.put_nowait(decoded)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error. Retrying after 5 seconds...", exc_info=True)
                await asyncio.sleep(5.0)
