#!/usr/bin/env python

import asyncio
import logging
import time
from typing import (
    AsyncIterable,
    Dict,
    Optional
)

import ujson
import aiohttp
from aiohttp import WSMsgType

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.connector.exchange.kucoin.kucoin_auth import KucoinAuth
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.kucoin import kucoin_constants as CONSTANTS
from hummingbot.core.utils.async_utils import safe_ensure_future


class KucoinAPIUserStreamDataSource(UserStreamTrackerDataSource):

    PING_TIMEOUT = 50.0

    _kausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._kausds_logger is None:
            cls._kausds_logger = logging.getLogger(__name__)
        return cls._kausds_logger

    def __init__(self, throttler: AsyncThrottler, kucoin_auth: KucoinAuth):
        self._throttler = throttler
        self._current_listen_key = None
        self._current_endpoint = None
        super().__init__()
        self._kucoin_auth: KucoinAuth = kucoin_auth
        self._last_recv_time: float = 0
        self._ping_pong_loop_task: Optional[asyncio.Future] = None

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def get_listen_key(self):
        async with aiohttp.ClientSession() as client:
            url = CONSTANTS.BASE_PATH_URL + CONSTANTS.PRIVATE_WS_DATA_PATH_URL
            header = self._kucoin_auth.add_auth_to_params("POST", CONSTANTS.PRIVATE_WS_DATA_PATH_URL)
            async with self._throttler.execute_task(CONSTANTS.PRIVATE_WS_DATA_PATH_URL):
                async with client.post(url, headers=header) as response:
                    response: aiohttp.ClientResponse = response
                    if response.status != 200:
                        raise IOError(f"Error fetching Kucoin user stream listen key. HTTP status is {response.status}.")
                    data: Dict[str, str] = await response.json()
                    return data

    async def _subscribe_topic(self, ws: aiohttp.ClientWebSocketResponse) -> AsyncIterable[str]:
        try:
            for topic in CONSTANTS.PRIVATE_ENDPOINT_NAMES:
                subscribe_request = {
                    "id": int(time.time()),
                    "type": "subscribe",
                    "topic": topic,
                    "privateChannel": True,
                    "response": True}
                async with self._throttler.execute_task(CONSTANTS.WS_REQUEST_LIMIT_ID):
                    await ws.send_json(subscribe_request)
        except asyncio.CancelledError:
            raise
        except Exception:
            return

    async def get_ws_connection(self, client: aiohttp.ClientSession) -> aiohttp.ClientWebSocketResponse:
        stream_url: str = f"{self._current_endpoint}?token={self._current_listen_key}&acceptUserMessage=true"
        self.logger().info(f"Connecting to {stream_url}.")

        async with self._throttler.execute_task(CONSTANTS.WS_CONNECTION_LIMIT_ID):
            return await client.ws_connect(stream_url, autoping=False)

    async def _inner_messages(self, ws: aiohttp.ClientWebSocketResponse) -> AsyncIterable[str]:
        while True:
            msg = await ws.receive()
            if msg.type == WSMsgType.CLOSED:
                raise ConnectionError
            self._last_recv_time = time.time()
            if msg.type == WSMsgType.PONG:
                continue
            yield msg.data

    async def listen_for_user_stream(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        while True:
            client = None
            ws = None
            try:
                if self._current_listen_key is None:
                    creds = await self.get_listen_key()
                    self._current_listen_key = creds["data"]["token"]
                    self._current_endpoint = creds["data"]["instanceServers"][0]["endpoint"]
                    self.logger().debug(f"Obtained listen key {self._current_listen_key}.")

                    client = aiohttp.ClientSession()
                    ws = await self.get_ws_connection(client)
                    await self._subscribe_topic(ws)
                    self._ping_pong_loop_task = safe_ensure_future(self._ping_pong_loop(ws))
                    async for msg in self._inner_messages(ws):
                        decoded: Dict[str, any] = ujson.loads(msg)
                        output.put_nowait(decoded)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error while maintaining the user event listen key. Retrying after "
                                    "5 seconds...", exc_info=False)
                await asyncio.sleep(5)
            finally:
                if ws is not None:
                    await ws.close()
                if client is not None:
                    await client.close()
                self._current_listen_key = None
                if self._ping_pong_loop_task is not None:
                    self._ping_pong_loop_task.cancel()
                    self._ping_pong_loop_task = None

    async def _ping_pong_loop(self, ws: aiohttp.ClientWebSocketResponse):
        while True:
            ping_send_time = time.time()
            await ws.ping()
            await asyncio.sleep(CONSTANTS.WS_PING_HEARTBEAT)
            if self._last_recv_time < ping_send_time:
                ws._pong_not_received()
                raise asyncio.TimeoutError
