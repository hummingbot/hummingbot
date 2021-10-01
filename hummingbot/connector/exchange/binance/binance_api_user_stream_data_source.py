#!/usr/bin/env python

import asyncio
import aiohttp
import logging
import time
import ujson

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
                response = await client.post(url=url,
                                             headers={"X-MBX-APIKEY": self._binance_client.API_KEY})

                if response.status != 200:
                    raise IOError(f"Error fetching user stream listen key. Response: {response}")
                data: Dict[str, str] = await response.json()
                return data["listenKey"]

    async def ping_listen_key(self, listen_key: str) -> bool:
        async with aiohttp.ClientSession() as client:
            async with self._throttler.execute_task(limit_id=CONSTANTS.BINANCE_USER_STREAM_PATH_URL):
                url = binance_utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_PATH_URL, domain=self._domain)
                response = await client.put(url=url,
                                            headers={"X-MBX-APIKEY": self._binance_client.API_KEY},
                                            params={"listenKey": listen_key})
                data: Tuple[str, any] = await response.json()
                if "code" in data:
                    self.logger().warning(f"Failed to refresh the listen key {listen_key}: {data}")
                    return False
                return True

    async def _create_websocket_connection(self) -> aiohttp.ClientWebSocketResponse:
        """
        Initialize WebSocket client for UserStreamDataSource
        """
        try:
            url = f"{CONSTANTS.WSS_URL.format(self._domain)}/{self._current_listen_key}"
            self.logger().info(f"Connecting to {url}.")
            return await aiohttp.ClientSession().ws_connect(url=url,
                                                            heartbeat=30.0,
                                                            autoping=False)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(f"Unexpected error occured when connecting to WebSocket server. Error: {e}")
            raise

    async def _iter_messages(self, ws: aiohttp.ClientWebSocketResponse) -> AsyncIterable[aiohttp.WSMessage]:
        try:
            while True:
                msg: aiohttp.WSMessage = await ws.receive()
                self._last_recv_time = time.time()
                yield msg
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(f"Unexpected error occured when parsing websocket payload. "
                                  f"Error: {e}")
            raise
        finally:
            await ws.close()

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

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                self._manage_listen_key_task = safe_ensure_future(self._manage_listen_key_task_loop())
                await self._listen_key_initialized_event.wait()

                self._ws = await self._create_websocket_connection()

                async for msg in self._iter_messages(self._ws):
                    output.put_nowait(ujson.loads(msg.data))
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error while listening to user stream. Retrying after 5 seconds... "
                                    f"Error: {e}",
                                    exc_info=True)
            finally:
                # Make sure no background task is leaked.
                self._manage_listen_key_task and self._manage_listen_key_task.cancel()
                self._current_listen_key = None
                self._listen_key_initialized_event.clear()
                await asyncio.sleep(5)
