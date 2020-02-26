#!/usr/bin/env python
import asyncio
import logging
import websockets
import ujson

from typing import Optional, AsyncIterable, Any
from websockets.exceptions import ConnectionClosed
from hummingbot.logger import HummingbotLogger
from hummingbot.market.bitfinex import BITFINEX_WS_URI
from hummingbot.market.bitfinex.bitfinex_auth import BitfinexAuth
from hummingbot.market.bitfinex.bitfinex_utils import merge_dicts

# reusable websocket class


class BitfinexWebsocket():
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, auth: Optional[BitfinexAuth]):
        self._client = None
        self._auth = auth

    # connect to exchange
    async def connect(self):
        try:
            self._client = await websockets.connect(BITFINEX_WS_URI)
            return self._client
        except Exception as e:
            self.logger().error(f"Websocket error: '{str(e)}'")

    # disconnect from exchange
    async def disconnect(self):
        if self._client is None:
            return

        self._client.close()

    # receive & parse messages
    async def _messages(self, condition: Optional[Any] = None) -> AsyncIterable[Any]:
        try:
            while True:
                try:
                    msg_str: str = await asyncio.wait_for(self._client.recv(), timeout=self.MESSAGE_TIMEOUT)
                    msg = ujson.loads(msg_str)

                    if (condition is None):
                        yield msg
                    # filter incoming messages
                    else:
                        try:
                            if (condition(msg) is True):
                                yield msg
                                return
                        except Exception:
                            pass

                except asyncio.TimeoutError:
                    try:
                        pong_waiter = await self._client.ping()
                        await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
                    except asyncio.TimeoutError:
                        raise
        except asyncio.TimeoutError:
            self.logger().error("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await self.disconnect()

    # emit messages
    async def _emit(self, data):
        await self._client.send(ujson.dumps(data))

    # subscribe: emit and yield results
    async def subscribe(self, channel: str, data: Any) -> AsyncIterable[Any]:
        await self._emit(merge_dicts(
            {
                "event": 'subscribe',
                "channel": channel
            },
            data
        ))

        async for msg in self._messages():
            yield msg

    # request: emit and wait for result once condition is met
    async def request(self, data: Any, condition: Optional[Any] = None) -> AsyncIterable[Any]:
        await self._emit(data)

        # TODO: handle timeout
        async for msg in self._messages(condition):
            yield msg

    # authenticate: authenticate session and optionally yield updates
    async def authenticate(self, keepAlive: bool = False) -> AsyncIterable[Any]:
        if self._auth is None:
            raise "auth not provided"

        payload = self._auth.generate_auth_payload('AUTH{nonce}'.format(nonce=self._auth.get_nonce()))

        def condition(msg):
            isAuthEvent = msg.get("event", None) == "auth"
            isStatusOk = msg.get("status", None) == "OK"

            return isAuthEvent and isStatusOk

        async for msg in self.request(payload, None if keepAlive else condition):
            yield msg
