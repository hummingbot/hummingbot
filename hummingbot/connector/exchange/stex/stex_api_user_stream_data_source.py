import asyncio
import aiohttp
import logging
from typing import (
    AsyncIterable,
    Dict,
    Optional,
    Any
)
import time
import ujson
import socketio
import pendulum
import requests
import os.path
import json
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.stex.stex_auth import StexAuth

STEX_WS_URL = "https://socket.stex.com"

JSON_SETTINGS = 'settings-websocket.json'
MESSAGE_TIMEOUT = 3.0
PING_TIMEOUT = 5.0

class StexAPIUserStreamDataSource(UserStreamTrackerDataSource):

    _stausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._stausds_logger is None:
            cls._stausds_logger = logging.getLogger(__name__)
        return cls._stausds_logger

    def __init__(self,stex_auth: StexAuth):
        self._shared_client: Optional[aiohttp.ClientSession] = None
        self._last_recv_time: float = 0
        self._auth_dict: Dict[str, Any] = stex_auth.generate_auth_dict()
        self.client: socketio.AsyncClient = socketio.AsyncClient()
        super().__init__()

    @property
    def last_recv_time(self):
        return self._last_recv_time

    async def get_access_token(self):
        return self._auth_dict["access_token"]

    async def _http_client(self) -> aiohttp.ClientSession:
        if self._shared_client is None or self._shared_client.closed:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def on_connect_stream(self):
        auth = {'headers': {'Authorization': 'Bearer ' + self._auth_dict['access_token']}}
        channel_name = 'private-user_orders_u_{}'.format(self._auth_dict['user_id'])
        await self.client.emit('subscribe',{'channel': channel_name,'auth': auth})

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                await self.client.connect(STEX_WS_URL,transports=["websocket"])
                self.client.on('connect',self.on_connect_stream)
                async def data_stream_callback(*msg):
                    self._last_recv_time = time.time()
                    output.put_nowait(msg)
                self.client.on(r"App\Events\UserOrder",data_stream_callback)
                await self.client.wait()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with Stex WebSocket connection. "
                                    "Retrying after 30 seconds...", exc_info=True)
                await asyncio.sleep(30.0)

    async def stop(self):
        if self._shared_client is not None and not self._shared_client.closed:
            await self._shared_client.close()
