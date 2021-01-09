#!/usr/bin/env python
import time
import asyncio
import logging
import websockets
import aiohttp
import ujson

from typing import Optional, List, AsyncIterable, Any
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.bitmax.bitmax_auth import BitmaxAuth
from hummingbot.connector.exchange.bitmax.bitmax_constants import REST_URL, getWsUrlPriv


class BitmaxAPIUserStreamDataSource(UserStreamTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 30.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, bitmax_auth: BitmaxAuth, trading_pairs: Optional[List[str]] = []):
        self._bitmax_auth: BitmaxAuth = bitmax_auth
        self._trading_pairs = trading_pairs
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._last_recv_time: float = 0
        super().__init__()

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue) -> AsyncIterable[Any]:
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """

        while True:
            try:
                response = await aiohttp.ClientSession().get(f"{REST_URL}/info", headers={
                    **self._bitmax_auth.get_headers(),
                    **self._bitmax_auth.get_auth_headers("info"),
                })
                info = await response.json()
                accountGroup = info.get("data").get("accountGroup")
                headers = self._bitmax_auth.get_auth_headers("stream")
                payload = {
                    "op": "sub",
                    "ch": "order:cash"
                }

                async with websockets.connect(f"{getWsUrlPriv(accountGroup)}/stream", extra_headers=headers) as ws:
                    try:
                        ws: websockets.WebSocketClientProtocol = ws
                        await ws.send(ujson.dumps(payload))

                        async for raw_msg in self._inner_messages(ws):
                            try:
                                msg = ujson.loads(raw_msg)
                                if (msg is None or (msg.get("m") != "order" and msg.get("m") != "cash")):
                                    continue

                                output.put_nowait(msg)
                            except Exception:
                                raise
                    except Exception:
                        raise
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(str(e))
                self.logger().error(
                    "Unexpected error with Bitmax WebSocket connection. " "Retrying after 30 seconds...", exc_info=True
                )
                await asyncio.sleep(30.0)

    async def _inner_messages(
        self,
        ws: websockets.WebSocketClientProtocol
    ) -> AsyncIterable[str]:
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                try:
                    raw_msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                    self._last_recv_time = time.time()
                    yield raw_msg
                except asyncio.TimeoutError:
                    try:
                        pong_waiter = await ws.ping()
                        await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
                        self._last_recv_time = time.time()
                    except asyncio.TimeoutError:
                        raise
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except websockets.ConnectionClosed:
            return
        finally:
            await ws.close()
