#!/usr/bin/env python
import asyncio
import copy
import logging
import websockets
import zlib
import ujson
import hummingbot.connector.exchange.digifinex.digifinex_constants as constants
# from hummingbot.core.utils.async_utils import safe_ensure_future


from typing import Optional, AsyncIterable, Any, List
from websockets.exceptions import ConnectionClosed
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.digifinex.digifinex_auth import DigifinexAuth
from hummingbot.connector.exchange.digifinex.digifinex_utils import RequestId

# reusable websocket class
# ToDo: We should eventually remove this class, and instantiate web socket connection normally (see Binance for example)


class DigifinexWebsocket(RequestId):
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
        self._WS_URL = constants.WSS_PRIVATE_URL if self._isPrivate else constants.WSS_PUBLIC_URL
        self._client: Optional[websockets.WebSocketClientProtocol] = None

    # connect to exchange
    async def connect(self):
        try:
            self._client = await websockets.connect(self._WS_URL)

            # if auth class was passed into websocket class
            # we need to emit authenticated requests
            if self._isPrivate:
                await self._emit("server.auth", None)
                # TODO: wait for response
                await asyncio.sleep(1)

            return self._client
        except Exception as e:
            self.logger().error(f"Websocket error: '{str(e)}'", exc_info=True)

    async def login(self):
        self._emit("server.auth", self._auth.generate_ws_signature())

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
                    raw_msg_bytes: bytes = await asyncio.wait_for(self._client.recv(), timeout=self.MESSAGE_TIMEOUT)
                    inflated_msg: bytes = zlib.decompress(raw_msg_bytes)
                    raw_msg = ujson.loads(inflated_msg)
                    # if "method" in raw_msg and raw_msg["method"] == "server.ping":
                    #     payload = {"id": raw_msg["id"], "method": "public/respond-heartbeat"}
                    #     safe_ensure_future(self._client.send(ujson.dumps(payload)))

                    if 'error' in raw_msg:
                        err = raw_msg['error']
                        if err is not None:
                            raise ConnectionError(raw_msg)
                        else:
                            continue    # ignore command success response

                    yield raw_msg
                except asyncio.TimeoutError:
                    await asyncio.wait_for(self._client.ping(), timeout=self.PING_TIMEOUT)
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        except Exception as e:
            _ = e
            raise
        finally:
            await self.disconnect()

    # emit messages
    async def _emit(self, method: str, data: Optional[Any] = {}) -> int:
        id = self.generate_request_id()

        payload = {
            "id": id,
            "method": method,
            "params": copy.deepcopy(data),
        }

        await self._client.send(ujson.dumps(payload))

        return id

    # request via websocket
    async def request(self, method: str, data: Optional[Any] = {}) -> int:
        return await self._emit(method, data)

    # subscribe to a method
    async def subscribe(self, category: str, channels: List[str]) -> int:
        return await self.request(category + ".subscribe", channels)

    # unsubscribe to a method
    async def unsubscribe(self, channels: List[str]) -> int:
        return await self.request("unsubscribe", {
            "channels": channels
        })

    # listen to messages by method
    async def on_message(self) -> AsyncIterable[Any]:
        async for msg in self._messages():
            yield msg
