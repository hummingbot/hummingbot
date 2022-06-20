#!/usr/bin/env python
import asyncio
import copy
import logging
import time
import zlib
from typing import Any, AsyncIterable, Dict, List, Optional

import aiohttp
import ujson

from hummingbot.connector.exchange.digifinex import digifinex_constants as CONSTANTS, digifinex_utils
from hummingbot.connector.exchange.digifinex.digifinex_auth import DigifinexAuth
from hummingbot.logger import HummingbotLogger


class DigifinexWebsocket():
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0
    _logger: Optional[HummingbotLogger] = None

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
        self._connection: Optional[aiohttp.ClientWebSocketResponse] = None
        self._last_recv_time: float = 0

    @property
    def last_recv_time(self):
        return self._last_recv_time

    # connect to exchange
    async def connect(self):
        try:
            self._connection = await self._client.ws_connect(self._WS_URL)
            if self._isPrivate:
                await self.login()
        except Exception as e:
            self.logger().error(f"Websocket error: '{str(e)}'", exc_info=True)
            raise

    async def login(self):
        await self.request("server.auth", self._auth.generate_ws_signature())
        response: aiohttp.WSMessage = await self.receive()
        if response is None or response.get("error") is not None:
            raise ConnectionError("Error authenticating to websocket connection...")

    # disconnect from exchange
    async def disconnect(self):
        if self._connection is None:
            return
        if self._client is None:
            return
        await self._connection.close()
        await self._client.close()

    async def ping(self):
        try:
            await self.request("server.ping", [])
        except Exception:
            self.logger().error("Error occurred sending ping request.",
                                exc_info=True)
            raise

    async def request(self, method: str, data: Optional[Any] = {}) -> int:
        request_id = digifinex_utils.generate_request_id()

        payload = {
            "id": request_id,
            "method": method,
            "params": copy.deepcopy(data),
        }

        self.logger().network(payload)
        await self._connection.send_str(ujson.dumps(payload))

        return request_id

    # subscribe to a method
    async def subscribe(self, category: str, channels: List[str]) -> int:
        await self.request(category + ".subscribe", channels)
        response: aiohttp.WSMessage = await self.receive()
        if response is None or response.get("error"):
            raise ConnectionError(f"Error subscribing to {category} {channels}...")

    # unsubscribe to a method
    async def unsubscribe(self, channels: List[str]) -> int:
        return await self.request("unsubscribe", {
            "channels": channels
        })

    def parse_message(self, raw_bytes: bytes) -> Dict[str, Any]:
        return ujson.loads(zlib.decompress(raw_bytes))

    async def receive(self) -> Dict[str, Any]:
        ws_msg: aiohttp.WSMessage = await self._connection.receive()
        if ws_msg.type == aiohttp.WSMsgType.CLOSED:
            self.logger().warning("Websocket server closed the connection")
            raise aiohttp.ClientConnectionError("Websocket server closed the connection")
        elif ws_msg.type == aiohttp.WSMsgType.BINARY:
            raw_msg: bytes = ws_msg.data
            self._last_recv_time = self._time()
            return self.parse_message(raw_msg)

    async def iter_messages(self) -> AsyncIterable[Any]:
        while True:
            try:
                msg: aiohttp.WSMessage = await asyncio.wait_for(self.receive(), timeout=self.MESSAGE_TIMEOUT)
                yield msg
            except asyncio.TimeoutError:
                await self.ping()

    def _time(self) -> float:
        return time.time()
