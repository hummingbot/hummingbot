import asyncio
from decimal import Decimal
import logging
import time
from typing import (
    AsyncIterable,
    Dict,
    Optional
)
import json
import simplejson
import websockets
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.ftx.ftx_auth import FtxAuth

FTX_API_ENDPOINT = "wss://ftx.com/ws/"
FTX_USER_STREAM_ENDPOINT = "userDataStream"


class FtxAPIUserStreamDataSource(UserStreamTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _bausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bausds_logger is None:
            cls._bausds_logger = logging.getLogger(__name__)
        return cls._bausds_logger

    def __init__(self, ftx_auth: FtxAuth):
        super().__init__()
        self._listen_for_user_stream_task = None
        self._ftx_auth: FtxAuth = ftx_auth
        self._last_recv_time: float = 0

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def set_subscriptions(self, ws: websockets.WebSocketClientProtocol):
        await ws.send(json.dumps(self._ftx_auth.generate_websocket_subscription()))
        await ws.send(json.dumps({"op": "subscribe", "channel": "orders"}))
        await ws.send(json.dumps({"op": "subscribe", "channel": "fills"}))

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                ws = await self.get_ws_connection()
                await self.set_subscriptions(ws)
                async for message in self._inner_messages(ws):
                    decoded: Dict[str, any] = simplejson.loads(message, parse_float=Decimal)
                    if decoded['type'] == 'error':
                        self.logger().warning(f"Error returned from ftx user stream: {decoded['code']}:{decoded['msg']}")
                    output.put_nowait(decoded)
            except asyncio.CancelledError:
                raise
            except asyncio.TimeoutError:
                self.logger().warning("WebSocket ping timed out. Reconnecting after 5 seconds...")
            except Exception:
                self.logger().error("Unexpected error while maintaining the user event listen key. Retrying after "
                                    "5 seconds...", exc_info=True)
            finally:
                await ws.close()
                await asyncio.sleep(5)

    async def _inner_messages(self, ws) -> AsyncIterable[str]:
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        while True:
            try:
                msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                self._last_recv_time = time.time()
                yield msg
            except asyncio.TimeoutError:
                pong_waiter = await ws.ping()
                await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
                self._last_recv_time = time.time()

    def get_ws_connection(self):
        stream_url: str = f"{FTX_API_ENDPOINT}"
        return websockets.connect(stream_url)
