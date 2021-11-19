#!/usr/bin/env python

import time
import asyncio
import logging
import aiohttp
import json

from hummingbot.connector.exchange.wazirx import wazirx_constants as CONSTANTS
from typing import Optional, Dict, AsyncIterable, Any
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.logger import HummingbotLogger
from .wazirx_auth import WazirxAuth


class WazirxAPIUserStreamDataSource(UserStreamTrackerDataSource):
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, wazirx_auth: WazirxAuth):
        super().__init__()
        self._wazirx_auth: WazirxAuth = wazirx_auth
        self._last_recv_time: float = 0
        self._auth_successful_event = asyncio.Event()
        self._throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self._shared_http_client = None

    @property
    def ready(self) -> bool:
        return self._last_recv_time > 0 and self._auth_successful_event.is_set()

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def _http_client(self) -> aiohttp.ClientSession:
        """
        :returns Shared client session instance
        """
        if self._shared_http_client is None:
            self._shared_http_client = aiohttp.ClientSession()
        return self._shared_http_client

    # generate auth token for private channels
    async def _get_wss_auth_token(self):
        async with self._throttler.execute_task(CONSTANTS.CREATE_WSS_AUTH_TOKEN):
            client = await self._http_client()
            url = f"{CONSTANTS.WAZIRX_API_BASE}/{CONSTANTS.CREATE_WSS_AUTH_TOKEN}"
            params = {}
            params = self._wazirx_auth.get_auth(params)
            headers = self._wazirx_auth.get_headers()
            response = await client.post(url, headers=headers, data=params)
            parsed_response = json.loads(await response.text())
            self._auth_successful_event.set()
            return parsed_response["auth_key"]

    async def _create_websocket_connection(self) -> aiohttp.ClientWebSocketResponse:
        """
        Initialize WebSocket client for APIOrderBookDataSource
        """
        try:
            return await aiohttp.ClientSession().ws_connect(url=CONSTANTS.WSS_URL)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(f"Unexpected error occured when connecting to WebSocket server. "
                                  f"Error: {e}")
            raise

    async def _iter_messages(self,
                             ws: aiohttp.ClientWebSocketResponse) -> AsyncIterable[Any]:
        try:
            while True:
                yield await ws.receive_json()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(f"Unexpected error occured when parsing websocket payload. "
                                  f"Error: {e}")
            raise
        finally:
            await ws.close()

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Subscribe to active orders via web socket
        """
        while True:
            try:
                ws = await self._create_websocket_connection()
                subscribe_request: Dict[str, Any] = {
                    "event": "subscribe",
                    "streams": ["outboundAccountPosition", "orderUpdate", "ownTrade"],
                    "auth_key": await self._get_wss_auth_token(),
                }
                await ws.send_json(subscribe_request)

                async for json_msg in self._iter_messages(ws):
                    self._last_recv_time = time.time()
                    output.put_nowait(json_msg)

            except asyncio.CancelledError:
                raise
            except asyncio.TimeoutError:
                self.logger().warning("WebSocket ping timed out. Reconnecting after 5 seconds...")
            except Exception:
                self.logger().error("Unexpected error while maintaining the user event listen key. Retrying after "
                                    "5 seconds...", exc_info=True)
            finally:
                self.logger().info("Closing")
                await ws.close()
                await asyncio.sleep(5)
