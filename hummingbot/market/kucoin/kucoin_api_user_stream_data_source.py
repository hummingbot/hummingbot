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
from websockets.exceptions import ConnectionClosed

from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
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

    async def ping_connection(self, ws: websockets.WebSocketClientProtocol) -> bool:
        while True:
            try:
                pong_waiter = await ws.ping()
                await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
                await self.wait_til_next_tick(seconds=40.0)
            except asyncio.TimeoutError:
                self.logger().warning(f"Failed to recieve pong response from server.")
                yield False
            yield True

    async def _subscribe_topic(self, ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        try:
            subscribe_request = {
                "id": int(time.time()),
                "type": "subscribe",
                "topic": "/spotMarket/tradeOrders",
                "privateChannel": True,
                "response": True}
            await ws.send(ujson.dumps(subscribe_request))
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().warning("Message recv() failed. Going to reconnect...", exc_info=True)
            return

    async def get_ws_connection(self) -> websockets.WebSocketClientProtocol:
        stream_url: str = f"{self._current_endpoint}?token={self._current_listen_key}&acceptUserMessage=true"
        self.logger().info(f"Connecting to {stream_url}.")

        # Create the WS connection.
        return websockets.connect(stream_url)

    async def _inner_messages(self, ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        while True:
            try:
                msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                self._last_recv_time = time.time()
                yield msg
            except asyncio.TimeoutError:
                self.logger().warning("Message recv() failed. Going to reconnect...", exc_info=True)
                return
            except asyncio.CancelledError:
                raise
            except ConnectionClosed:
                return
            finally:
                await ws.close()

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        try:
            while True:
                try:
                    if self._current_listen_key is None:
                        creds = await self.get_listen_key()
                        self._current_listen_key = creds["data"]["token"]
                        self._current_endpoint = creds["data"]["instanceServers"][0]["endpoint"]
                        self.logger().debug(f"Obtained listen key {self._current_listen_key}.")

                    success: bool = False
                    async with (await self.get_ws_connection()) as ws:
                        await self._subscribe_topic(ws)
                        async for msg in self.ping_connection(ws):
                            success = msg
                            if not success:
                                self._current_listen_key = None
                                self.logger().debug(f"Refreshing websocket connection.")
                                continue
                        async for msg in self._inner_messages(ws):
                            decoded: Dict[str, any] = ujson.loads(msg)
                            output.put_nowait(decoded)

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
