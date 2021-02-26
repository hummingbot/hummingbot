# -*- coding: utf-8 -*-

import logging
import asyncio
import time
import json
import websockets

from typing import AsyncIterable, Optional, List
from websockets.exceptions import ConnectionClosed

from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather

from hummingbot.connector.exchange.beaxy.beaxy_auth import BeaxyAuth
from hummingbot.connector.exchange.beaxy.beaxy_constants import BeaxyConstants


class BeaxyAPIUserStreamDataSource(UserStreamTrackerDataSource):
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _bxyausds_logger: Optional[logging.Logger] = None

    @classmethod
    def logger(cls) -> logging.Logger:
        if cls._bxyausds_logger is None:
            cls._bxyausds_logger = logging.getLogger(__name__)
        return cls._bxyausds_logger

    def __init__(self, beaxy_auth: BeaxyAuth, trading_pairs: Optional[List[str]] = []):
        self._beaxy_auth: BeaxyAuth = beaxy_auth
        self._trading_pairs = trading_pairs
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._last_recv_time: float = 0
        super().__init__()

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def __listen_ws(self, url: str):
        while True:
            try:
                token = await self._beaxy_auth.get_token()
                async with websockets.connect(url.format(access_token=token)) as ws:
                    async for raw_msg in self._inner_messages(ws):
                        msg = json.loads(raw_msg)  # ujson may round floats uncorrectly
                        if msg.get('type') == 'keep_alive':
                            continue
                        yield msg
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error('Unexpected error with Beaxy connection. '
                                    'Retrying after 30 seconds...', exc_info=True)
                await asyncio.sleep(30.0)

    async def _listen_for_balance(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        async for msg in self.__listen_ws(BeaxyConstants.TradingApi.WS_BALANCE_ENDPOINT):
            output.put_nowait([BeaxyConstants.UserStream.BALANCE_MESSAGE, msg])

    async def _listen_for_orders(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        async for msg in self.__listen_ws(BeaxyConstants.TradingApi.WS_ORDERS_ENDPOINT):
            output.put_nowait([BeaxyConstants.UserStream.ORDER_MESSAGE, msg])

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """
        await safe_gather(
            self._listen_for_balance(ev_loop, output),
            self._listen_for_orders(ev_loop, output),
        )

    async def _inner_messages(self,
                              ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        """
        Generator function that returns messages from the web socket stream
        :param ws: current web socket connection
        :returns: message in AsyncIterable format
        """
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                    self._last_recv_time = time.time()
                    yield msg
                except asyncio.TimeoutError:
                    try:
                        pong_waiter = await ws.ping()
                        self._last_recv_time = time.time()
                        await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
                    except asyncio.TimeoutError:
                        raise
        except asyncio.TimeoutError:
            self.logger().warning('WebSocket ping timed out. Going to reconnect...')
            return
        except ConnectionClosed:
            return
        finally:
            await ws.close()
