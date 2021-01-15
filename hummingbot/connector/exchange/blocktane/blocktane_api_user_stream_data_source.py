#!/usr/bin/env python

import asyncio
import logging
import time
import ujson
import websockets
from typing import (
    AsyncIterable,
    Dict,
    Optional,
    List
)

from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.connector.exchange.blocktane.blocktane_auth import BlocktaneAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger

WS_BASE_URL = "wss://trade.blocktane.io/api/v2/ws/private/?stream=order&stream=trade&stream=balance"


class BlocktaneAPIUserStreamDataSource(UserStreamTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _bausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bausds_logger is None:
            cls._bausds_logger = logging.getLogger(__name__)
        return cls._bausds_logger

    def __init__(self, blocktane_auth: BlocktaneAuth, trading_pairs: Optional[List[str]] = None):
        self._blocktane_auth: BlocktaneAuth = blocktane_auth
        self._listen_for_user_stream_task = None
        self._last_recv_time: float = 0
        super().__init__()

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    @staticmethod
    async def wait_til_next_tick(seconds: float = 1.0):
        now: float = time.time()
        current_tick: int = int(now // seconds)
        delay_til_next_tick: float = (current_tick + 1) * seconds - now
        await asyncio.sleep(delay_til_next_tick)

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                if self._listen_for_user_stream_task is not None:
                    self._listen_for_user_stream_task.cancel()
                self._listen_for_user_stream_task = safe_ensure_future(self.log_user_stream(output))
                await self.wait_til_next_tick(seconds=60.0)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error while maintaining the user event listen key. Retrying after "
                                    "5 seconds...", exc_info=True)
                await asyncio.sleep(5)

    async def _inner_messages(self, ws) -> AsyncIterable[str]:
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
            raise
        except websockets.exceptions.ConnectionClosed:
            raise
        finally:
            await ws.close()

    async def messages(self) -> AsyncIterable[str]:
        ws = await self.get_ws_connection()
        while(True):
            async for msg in self._inner_messages(ws):
                yield msg

    def get_ws_connection(self):
        ws = websockets.connect(WS_BASE_URL, extra_headers=self._blocktane_auth.generate_auth_dict())

        return ws

    async def log_user_stream(self, output: asyncio.Queue):
        while True:
            try:
                async for message in self.messages():
                    decoded: Dict[str, any] = ujson.loads(message)
                    output.put_nowait(decoded)
            except Exception:
                self.logger().error("Unexpected error. Retrying after 5 seconds...", exc_info=True)
                await asyncio.sleep(5.0)
