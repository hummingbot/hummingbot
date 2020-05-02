#!/usr/bin/env python

import asyncio
import aiohttp
import logging
import time
from typing import (
    AsyncIterable,
    Dict,
    Optional
)
import ujson
import websockets

from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.market.kucoin.kucoin_auth import KucoinAuth
from hummingbot.logger import HummingbotLogger

KUCOIN_API_ENDPOINT = "https://api.kucoin.com"
KUCOIN_USER_STREAM_ENDPOINT = "/api/v1/bullet-private"


class KucoinAPIUserStreamDataSource(UserStreamTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 50.0

    _kausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._kausds_logger is None:
            cls._kausds_logger = logging.getLogger(__name__)
        return cls._kausds_logger

    def __init__(self, kucoin_auth: KucoinAuth):
        self._current_listen_key = None
        self._current_endpoint = None
        self._listen_for_user_stream_task = None
        super().__init__()
        self._kucoin_auth: KucoinAuth = kucoin_auth
        self._last_recv_time: float = 0

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def get_listen_key(self):
        async with aiohttp.ClientSession() as client:
            header = self._kucoin_auth.add_auth_to_params("POST", KUCOIN_USER_STREAM_ENDPOINT)
            async with client.post(f"{KUCOIN_API_ENDPOINT}{KUCOIN_USER_STREAM_ENDPOINT}", headers=header) as response:
                response: aiohttp.ClientResponse = response
                if response.status != 200:
                    raise IOError(f"Error fetching Kucoin user stream listen key. HTTP status is {response.status}.")
                data: Dict[str, str] = await response.json()
                return data

    async def ping_listen_key(self, ws: websockets.WebSocketClientProtocol) -> bool:
        try:
            pong_waiter = await ws.ping()
            await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
        except asyncio.TimeoutError:
            self.logger().warning(f"Failed to recieve pong response from server.")
            return False
        return True

    async def _inner_messages(self, ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        try:
            while True:
                msg = await ws.recv()
                self._last_recv_time = time.time()
                yield msg
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().warning("Message recv() failed. Going to reconnect...", exc_info=True)
            return

    async def messages(self) -> AsyncIterable[str]:
        try:
            async with (await self.get_ws_connection()) as ws:
                async for msg in self._inner_messages(ws):
                    yield msg
        except asyncio.CancelledError:
            raise

    async def get_ws_connection(self) -> websockets.WebSocketClientProtocol:
        stream_url: str = f"{self._current_endpoint}?token={self._current_listen_key}&acceptUserMessage=true"
        self.logger().info(f"Reconnecting to {stream_url}.")

        # Create the WS connection.
        return websockets.connect(stream_url)

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        try:
            while True:
                try:
                    if self._current_listen_key is None:
                        creds = await self.get_listen_key()
                        self._current_listen_key = creds["data"]["token"]
                        self._current_endpoint = creds["data"]["instanceServers"][0]["endpoint"]
                        self.logger().debug(f"Obtained listen key {self._current_listen_key}.")
                        if self._listen_for_user_stream_task is not None:
                            self._listen_for_user_stream_task.cancel()
                        self._listen_for_user_stream_task = safe_ensure_future(self.log_user_stream(output))
                        await self.wait_til_next_tick(seconds=40.0)

                    success: bool = False
                    async with (await self.get_ws_connection()) as ws2:
                        success = await self.ping_listen_key(ws2)
                    if not success:
                        print("No pong")
                        self._current_listen_key = None
                        if self._listen_for_user_stream_task is not None:
                            self._listen_for_user_stream_task.cancel()
                            self._listen_for_user_stream_task = None
                        continue
                    self.logger().debug(f"Refreshed listen key {self._current_listen_key}.")

                    await self.wait_til_next_tick(seconds=40.0)
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
