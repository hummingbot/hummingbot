#!/usr/bin/env python
import asyncio
import copy
import logging
import websockets
import zlib
import ujson
from asyncio import InvalidStateError
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
    disconnect_future: asyncio.Future = None
    tasks: [asyncio.Task] = []
    login_msg_id: int = 0

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
        if self.disconnect_future is not None:
            raise InvalidStateError('already connected')
        self.disconnect_future = asyncio.Future()

        try:
            self._client = await websockets.connect(self._WS_URL)

            # if auth class was passed into websocket class
            # we need to emit authenticated requests
            if self._isPrivate:
                await self.login()
                self.tasks.append(asyncio.create_task(self._ping_loop()))

            return self._client
        except Exception as e:
            self.logger().error(f"Websocket error: '{str(e)}'", exc_info=True)

    async def login(self):
        self.login_msg_id = await self._emit("server.auth", self._auth.generate_ws_signature())
        msg = await self._messages()
        if msg is None:
            raise ConnectionError('websocket auth failed: connection closed unexpectedly')
        if msg.get('error') is not None:
            raise ConnectionError(f'websocket auth failed: {msg}')

    # disconnect from exchange
    async def disconnect(self):
        if self._client is None:
            return

        await self._client.close()
        if not self.disconnect_future.done:
            self.disconnect_future.result(True)
        if len(self.tasks) > 0:
            await asyncio.wait(self.tasks)

    async def _ping_loop(self):
        while True:
            try:
                disconnected = await asyncio.wait_for(self.disconnect_future, 30)
                _ = disconnected
                break
            except asyncio.TimeoutError:
                await self._emit('server.ping', [])
                # msg = await self._messages() # concurrent read not allowed

    # receive & parse messages
    async def _messages(self) -> Any:
        try:
            success = False
            while True:
                try:
                    raw_msg_bytes: bytes = await asyncio.wait_for(self._client.recv(), timeout=self.MESSAGE_TIMEOUT)
                    inflated_msg: bytes = zlib.decompress(raw_msg_bytes)
                    raw_msg = ujson.loads(inflated_msg)
                    # if "method" in raw_msg and raw_msg["method"] == "server.ping":
                    #     payload = {"id": raw_msg["id"], "method": "public/respond-heartbeat"}
                    #     safe_ensure_future(self._client.send(ujson.dumps(payload)))
                    # self.logger().debug(inflated_msg)
                    # method = raw_msg.get('method')
                    # if method not in ['depth.update', 'trades.update']:
                    #     self.logger().network(inflated_msg)

                    err = raw_msg.get('error')
                    if err is not None:
                        raise ConnectionError(raw_msg)
                    elif raw_msg.get('result') == 'pong':
                        continue    # ignore ping response

                    success = True
                    return raw_msg
                except asyncio.TimeoutError:
                    await asyncio.wait_for(self._client.ping(), timeout=self.PING_TIMEOUT)
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        except Exception as e:
            _ = e
            self.logger().exception('digifinex.websocket._messages', stack_info=True)
            raise
        finally:
            if not success:
                await self.disconnect()

    # emit messages
    async def _emit(self, method: str, data: Optional[Any] = {}) -> int:
        id = self.generate_request_id()

        payload = {
            "id": id,
            "method": method,
            "params": copy.deepcopy(data),
        }

        req = ujson.dumps(payload)
        self.logger().network(req)   # todo remove log
        await self._client.send(req)

        return id

    # request via websocket
    async def request(self, method: str, data: Optional[Any] = {}) -> int:
        return await self._emit(method, data)

    # subscribe to a method
    async def subscribe(self, category: str, channels: List[str]) -> int:
        id = await self.request(category + ".subscribe", channels)
        msg = await self._messages()
        if msg.get('error') is not None:
            raise ConnectionError(f'subscribe {category} {channels} failed: {msg}')
        return id

    # unsubscribe to a method
    async def unsubscribe(self, channels: List[str]) -> int:
        return await self.request("unsubscribe", {
            "channels": channels
        })

    # listen to messages by method
    async def on_message(self) -> AsyncIterable[Any]:
        while True:
            msg = await self._messages()
            if msg is None:
                return
            if 'pong' in str(msg):
                _ = int(0)
            yield msg
