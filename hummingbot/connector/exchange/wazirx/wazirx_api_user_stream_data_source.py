#!/usr/bin/env python

import time
import asyncio
import logging
import aiohttp
import websockets
import simplejson
import ujson
import json

from websockets.exceptions import ConnectionClosed
from hummingbot.connector.exchange.wazirx import wazirx_constants as CONSTANTS
from decimal import Decimal
from typing import Optional, Dict, AsyncIterable, Any
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
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

    @property
    def ready(self) -> bool:
        return self.last_recv_time > 0 and self._auth_successful_event.is_set()

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    # generate auth token for private channels
    async def _get_wss_auth_token(self):
        async with aiohttp.ClientSession() as client:
            url = f"{CONSTANTS.WAZIRX_API_BASE}/{CONSTANTS.CREATE_WSS_AUTH_TOKEN}"
            params = {}
            params = self._wazirx_auth.get_auth(params)
            headers = self._wazirx_auth.get_headers()
            response = await client.post(url, headers=headers, data=params)
            parsed_response = json.loads(await response.text())
            self._auth_successful_event.set()
            return parsed_response["auth_key"]

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
        except ConnectionClosed:
            return
        finally:
            await ws.close()

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Subscribe to active orders via web socket
        """
        while True:
            try:
                ws = await self.get_ws_connection()
                subscribe_request: Dict[str, Any] = {
                    "event": "subscribe",
                    "streams": ["outboundAccountPosition", "orderUpdate", "ownTrade"],
                    "auth_key": await self._get_wss_auth_token(),
                }
                await ws.send(ujson.dumps(subscribe_request))

                async for raw_msg in self._inner_messages(ws):
                    msg = simplejson.loads(raw_msg, parse_float=Decimal)
                    output.put_nowait(msg)

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

    def get_ws_connection(self):
        stream_url: str = f"{CONSTANTS.WSS_URL}"
        return websockets.connect(stream_url)
