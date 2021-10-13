import aiohttp
import asyncio
import logging
import time

import hummingbot.connector.derivative.binance_perpetual.constants as CONSTANTS

from typing import (
    Any,
    AsyncIterable,
    Dict,
    Optional,
    Tuple,
)

from hummingbot.connector.derivative.binance_perpetual import binance_perpetual_utils as utils
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger


class BinancePerpetualUserStreamDataSource(UserStreamTrackerDataSource):

    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800  # Recommended to Ping/Update listen key to keep connection alive
    HEARTBEAT_TIME_INTERVAL = 30.0

    _bpusds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bpusds_logger is None:
            cls._bpusds_logger = logging.getLogger(__name__)
        return cls._bpusds_logger

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    def __init__(self, api_key: str, domain: str = "binance_perpetual", throttler: Optional[AsyncThrottler] = None):
        super().__init__()
        self._api_key: str = api_key
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._last_recv_time: float = 0
        self._domain = domain
        self._throttler = throttler or self._get_throttler_instance()

        self._ws = None
        self._manage_listen_key_task = None
        self._last_listen_key_ping_ts = 0
        self._listen_key_initialized_event: asyncio.Event = asyncio.Event()

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        return AsyncThrottler(CONSTANTS.RATE_LIMITS)

    async def get_listen_key(self):
        async with aiohttp.ClientSession() as client:
            async with self._throttler.execute_task(limit_id=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT):
                response: aiohttp.ClientResponse = await client.post(
                    url=utils.rest_url(CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, self._domain),
                    headers={"X-MBX-APIKEY": self._api_key},
                )
                if response.status != 200:
                    raise IOError(
                        f"Error fetching Binance Perpetual user stream listen key. "
                        f"HTTP status is {response.status}."
                    )
                data: Dict[str, str] = await response.json()
                return data["listenKey"]

    async def ping_listen_key(self) -> bool:
        async with aiohttp.ClientSession() as client:
            async with self._throttler.execute_task(limit_id=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT):
                url = utils.rest_url(CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, self._domain)
                response: aiohttp.ClientResponse = await client.put(url=url,
                                                                    headers={"X-MBX-APIKEY": self._api_key},
                                                                    params={"listenKey": self._current_listen_key})
                data: Tuple[str, Any] = await response.json()
                if "code" in data:
                    self.logger().warning(f"Failed to refresh the listen key {self._current_listen_key}: {data}")
                    return False
                return True

    async def _create_websocket_connection(self) -> aiohttp.ClientWebSocketResponse:
        """
        Initialize WebSocket client for UserStreamDataSource
        """
        try:
            url = f"{utils.wss_url(CONSTANTS.PRIVATE_WS_ENDPOINT, self._domain)}/{self._current_listen_key}"
            self.logger().info(f"Connecting to {url}.")
            return await aiohttp.ClientSession().ws_connect(
                url=url, heartbeat=self.HEARTBEAT_TIME_INTERVAL, autoping=False
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(f"Unexpected error occured when connecting to WebSocket server. Error: {e}")
            raise

    async def _iter_messages(self, ws: aiohttp.ClientWebSocketResponse) -> AsyncIterable[aiohttp.WSMessage]:
        try:
            while True:
                raw_msg: aiohttp.WSMessage = await ws.receive()
                self._last_recv_time = time.time()
                yield raw_msg
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(f"Unexpected error occurred when parsing websocket payload. "
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
        except Exception as e:
            self.logger().error(f"Unexpected error occurred with maintaining listen key. "
                                f"Error {e}")
            raise
        finally:
            self._current_listen_key = None
            self._listen_key_initialized_event.clear()
            self._ws and await self._ws.close()

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                self._manage_listen_key_task = safe_ensure_future(self._manage_listen_key_task_loop())
                await self._listen_key_initialized_event.wait()

                self._ws = await self._create_websocket_connection()

                async for msg in self._iter_messages(self._ws):
                    if msg.type == aiohttp.WSMsgType.PING:
                        self.logger().debug("Received PING frame. Sending PONG frame...")
                        await self._ws.pong()
                        continue
                    if msg.type == aiohttp.WSMsgType.PONG:
                        self.logger().debug("Received PONG frame.")
                        continue
                    output.put_nowait(msg.json())
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(
                    f"Unexpected error while listening to user stream. Retrying after 5 seconds... "
                    f"Error: {e}",
                    exc_info=True,
                )
            finally:
                # Make sure no background task is leaked.
                self._ws and await self._ws.close()
                self._manage_listen_key_task and self._manage_listen_key_task.cancel()
                self._current_listen_key = None
                self._listen_key_initialized_event.clear()
                self._last_recv_time = 0
                await self._sleep(5)
