# -*- coding: utf-8 -*-

import logging
import asyncio
import time
import ujson
import websockets

from typing import AsyncIterable, Optional, List
from websockets.exceptions import ConnectionClosed

from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce

from hummingbot.connector.exchange.beaxy.beaxy_auth import BeaxyAuth
from hummingbot.connector.exchange.beaxy.beaxy_constants import BeaxyConstants
from hummingbot.connector.exchange.beaxy.beaxy_stomp_message import BeaxyStompMessage


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

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """
        while True:
            try:
                async with websockets.connect(BeaxyConstants.TradingApi.WS_BASE_URL) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    connect_request = BeaxyStompMessage('CONNECT')
                    connect_request.headers = await self._beaxy_auth.generate_ws_auth_dict()
                    await ws.send(connect_request.serialize())

                    orders_sub_request = BeaxyStompMessage('SUBSCRIBE')
                    orders_sub_request.headers['id'] = f'sub-humming-{get_tracking_nonce()}'
                    orders_sub_request.headers['destination'] = '/user/v1/orders'
                    orders_sub_request.headers['X-Deltix-Nonce'] = str(get_tracking_nonce())
                    await ws.send(orders_sub_request.serialize())

                    async for raw_msg in self._inner_messages(ws):
                        stomp_message = BeaxyStompMessage.deserialize(raw_msg)
                        if stomp_message.has_error():
                            raise Exception(f'Got error from ws. Headers - {stomp_message.headers}')

                        msg = ujson.loads(stomp_message.body)
                        output.put_nowait(msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error('Unexpected error with Beaxy connection. '
                                    'Retrying after 30 seconds...', exc_info=True)
                await asyncio.sleep(30.0)

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
