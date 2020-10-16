#!/usr/bin/env python
import asyncio
import copy
import logging
import websockets
import ujson
import hummingbot.connector.exchange.probit.probit_constants as constants


from typing import Optional, AsyncIterable, Any
from websockets.exceptions import ConnectionClosed
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.probit.probit_auth import ProbitAuth
from hummingbot.connector.exchange.probit.probit_utils import RequestId

# reusable websocket class


class ProbitWebsocket(RequestId):
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, auth: Optional[ProbitAuth] = None):
        self._auth: Optional[ProbitAuth] = auth
        self._isPrivate = True if self._auth is not None else False
        self._WS_URL = constants.WSS_URL
        self._client: Optional[websockets.WebSocketClientProtocol] = None

    # connect to exchange
    async def connect(self):
        try:
            self._client = await websockets.connect(self._WS_URL)

            # if auth class was passed into websocket class
            # we need to emit authenticated requests
            if self._isPrivate:
                auth_dict = await self._auth.generate_auth_dict()
                data = {"token": auth_dict["access_token"]}
                await self._emit("authorization", data)
                # TODO: wait for response
                await asyncio.sleep(1)

            return self._client
        except Exception as e:
            self.logger().error(f"Websocket error: '{str(e)}'", exc_info=True)

    # disconnect from exchange
    async def disconnect(self):
        if self._client is None:
            return

        await self._client.close()

    # receive & parse messages
    async def _messages(self) -> AsyncIterable[Any]:
        try:
            while True:
                try:
                    raw_msg_str: str = await asyncio.wait_for(self._client.recv(), timeout=self.MESSAGE_TIMEOUT)
                    raw_msg = ujson.loads(raw_msg_str)
                    yield raw_msg
                except asyncio.TimeoutError:
                    await asyncio.wait_for(self._client.ping(), timeout=self.PING_TIMEOUT)
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await self.disconnect()

    # emit messages
    async def _emit(self, method: str, data: Optional[Any] = {}) -> None:
        payload = copy.deepcopy(data)
        payload["type"] = method
        await self._client.send(ujson.dumps(payload))

    # request via websocket
    async def request(self, method: str, data: Optional[Any] = {}) -> None:
        return await self._emit(method, data)

    # subscribe to a method
    async def subscribe(self, channel: str, data: Optional[Any] = {}) -> None:
        payload = copy.deepcopy(data)
        payload["channel"] = channel
        return await self.request("subscribe", payload)

    # unsubscribe to a method
    async def unsubscribe(self, channel: str, data: Optional[Any] = {}) -> None:
        payload = copy.deepcopy(data)
        payload["channel"] = channel
        return await self.request("unsubscribe", payload)

    # listen to messages by method
    async def on_message(self) -> AsyncIterable[Any]:
        async for msg in self._messages():
            yield msg
