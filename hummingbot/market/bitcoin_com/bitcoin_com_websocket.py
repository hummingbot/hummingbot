#!/usr/bin/env python
import asyncio
import logging
import websockets
import ujson
import hummingbot.market.bitcoin_com.bitcoin_com_constants as constants

from typing import Dict, Optional, AsyncIterable, Any
from websockets.exceptions import ConnectionClosed
from hummingbot.logger import HummingbotLogger
from hummingbot.market.bitcoin_com.bitcoin_com_utils import raw_to_response

# reusable websocket class


class BitcoinComWebsocket():
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self):
        self._client: Optional[websockets.WebSocketClientProtocol] = None
        self._events: Dict[str, bool] = {}
        self._nonce = 0

    def _get_event(self, name: str):
        return self._events.get(name)

    def _set_event(self, name: str):
        self._events[name] = True

    # connect to exchange
    async def connect(self):
        try:
            self._client = await websockets.connect(constants.WSS_URL)
            return self._client
        except Exception as e:
            self.logger().error(f"Websocket error: '{str(e)}'", exc_info=True)

    # disconnect from exchange
    async def disconnect(self):
        if self._client is None:
            return

        self._client.close()

    # receive & parse messages
    async def _messages(self) -> AsyncIterable[Any]:
        try:
            while True:
                try:
                    raw_msg_str: str = await asyncio.wait_for(self._client.recv(), timeout=self.MESSAGE_TIMEOUT)
                    raw_msg = ujson.loads(raw_msg_str)

                    yield raw_to_response(raw_msg)
                except asyncio.TimeoutError:
                    try:
                        pong_waiter = await self._client.ping()
                        await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
                    except asyncio.TimeoutError:
                        raise
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await self.disconnect()

    # emit messages
    async def _emit(self, name: str, data) -> int:
        self._nonce += 1

        await self._client.send(ujson.dumps({
            "method": name,
            "id": self._nonce,
            "params": data
        }))

        return self._nonce

    # request data and return result
    async def request(self, name: str, data) -> Any:
        nonce = await self._emit(name, data)

        async for msg in self._messages():
            if (msg["id"] == nonce):
                yield msg

    # subscribe to a method
    async def subscribe(self, name: str, data) -> int:
        return await self._emit(name, data)

    # listen to messages by method
    async def on(self, name: str) -> AsyncIterable[Any]:
        self._set_event(name)

        async for msg in self._messages():
            if (msg["method"] == name):
                yield msg

    # authenticate connection and return result
    async def authenticate(self, api_key: str, secret_key: str) -> bool:
        async for result in self.request("login", {
            "algo": "BASIC",
            "pKey": api_key,
            "sKey": secret_key
        }):
            yield result
