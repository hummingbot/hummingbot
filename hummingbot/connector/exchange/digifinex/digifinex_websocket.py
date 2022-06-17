#!/usr/bin/env python
import asyncio
import copy
import logging
import time
import zlib
from typing import Any, AsyncIterable, Dict, List, Optional

import aiohttp
import ujson

from hummingbot.connector.exchange.digifinex import digifinex_constants as CONSTANTS
from hummingbot.connector.exchange.digifinex.digifinex_auth import DigifinexAuth
from hummingbot.connector.exchange.digifinex.digifinex_utils import RequestId
from hummingbot.logger import HummingbotLogger


class DigifinexWebsocket(RequestId):
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0
    _logger: Optional[HummingbotLogger] = None
    disconnect_future: asyncio.Future = None
    tasks: List[asyncio.Task] = []
    login_msg_id: int = 0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, auth: Optional[DigifinexAuth] = None):
        self._auth: Optional[DigifinexAuth] = auth
        self._isPrivate = True if self._auth is not None else False
        self._WS_URL = CONSTANTS.WSS_PRIVATE_URL if self._isPrivate else CONSTANTS.WSS_PUBLIC_URL
        self._client: aiohttp.ClientSession = aiohttp.ClientSession()
        self._websocket: Optional[aiohttp.ClientWebSocketResponse] = None
        self._last_recv_time: float = 0

    @property
    def last_recv_time(self):
        return self._last_recv_time

    # connect to exchange
    async def connect(self):
        try:
            self._websocket = await aiohttp.ClientSession().ws_connect(self._WS_URL)
            if self._isPrivate:
                await self.login()

            return self._client
        except Exception as e:
            self.logger().error(f"Websocket error: '{str(e)}'", exc_info=True)

    async def login(self):
        self.login_msg_id = await self.request("server.auth", self._auth.generate_ws_signature())
        raw_bytes = await self._websocket.receive_bytes()
        parse_msg = self.parse_message(raw_bytes)
        self._last_recv_time = self._time()
        if parse_msg is None:
            raise ConnectionError('websocket auth failed: connection closed unexpectedly')
        if parse_msg.get('error') is not None:
            raise ConnectionError(f'websocket auth failed: {parse_msg}')

    # disconnect from exchange
    async def disconnect(self):
        if self._websocket is None:
            return
        if self._client is None:
            return
        await self._websocket.close()
        await self._client.close()
        for task in self.tasks:
            task.cancel()

    async def ping(self):
        try:
            await self.request("server.ping", [])
        except Exception:
            self.logger().error("Error occurred sending ping request.",
                                exc_info=True)
            raise

    async def request(self, method: str, data: Optional[Any] = {}) -> int:
        request_id = self.generate_request_id()

        payload = {
            "id": request_id,
            "method": method,
            "params": copy.deepcopy(data),
        }

        self.logger().network(payload)
        await self._websocket.send_str(ujson.dumps(payload))

        return request_id

    # subscribe to a method
    async def subscribe(self, category: str, channels: List[str]) -> int:
        request_id = await self.request(category + ".subscribe", channels)
        raw_msg: bytes = await self._websocket.receive_bytes()
        parse_msg = self.parse_message(raw_msg)
        if parse_msg.get('error') is not None:
            raise ConnectionError(f'subscribe {category} {channels} failed: {parse_msg}')
        return request_id

    # unsubscribe to a method
    async def unsubscribe(self, channels: List[str]) -> int:
        return await self.request("unsubscribe", {
            "channels": channels
        })

    def parse_message(self, raw_bytes: bytes) -> Dict[str, Any]:
        return ujson.loads(zlib.decompress(raw_bytes))

    async def iter_messages(self) -> AsyncIterable[Any]:
        while True:
            try:
                ws_msg: aiohttp.WSMessage = await asyncio.wait_for(self._websocket.receive(), timeout=300)

                if ws_msg.type == aiohttp.WSMsgType.BINARY:
                    raw_msg: bytes = ws_msg.data
                    parse_msg: Dict[str, Any] = self.parse_message(raw_msg)
                    err = parse_msg.get('error')
                    if err is not None:
                        raise ConnectionError(parse_msg)
                    elif parse_msg.get('result') == 'pong':
                        continue
                elif ws_msg.type == aiohttp.WSMsgType.CLOSED:
                    self.logger().warning("Websocket server closed the connection")
                    raise aiohttp.ClientConnectionError("Websocket server closed the connection")

                self._last_recv_time = self._time()
                yield parse_msg
            except asyncio.TimeoutError:
                await self.ping()

    def _time(self) -> float:
        return time.time()
