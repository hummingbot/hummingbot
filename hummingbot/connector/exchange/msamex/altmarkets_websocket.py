#!/usr/bin/env python
import asyncio
import logging
import websockets
import json
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.utils.async_utils import safe_ensure_future
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional,
)
from websockets.exceptions import ConnectionClosed
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.msamex.msamex_constants import Constants
from hummingbot.connector.exchange.msamex.msamex_auth import mSamexAuth
from hummingbot.connector.exchange.msamex.msamex_utils import RequestId

# reusable websocket class
# ToDo: We should eventually remove this class, and instantiate web socket connection normally (see Binance for example)


class mSamexWebsocket(RequestId):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 auth: Optional[mSamexAuth] = None,
                 throttler: Optional[AsyncThrottler] = None):
        self._auth: Optional[mSamexAuth] = auth
        self._isPrivate = True if self._auth is not None else False
        self._WS_URL = Constants.WS_PRIVATE_URL if self._isPrivate else Constants.WS_PUBLIC_URL
        self._client: Optional[websockets.WebSocketClientProtocol] = None
        self._is_subscribed = False
        self._throttler = throttler or AsyncThrottler(Constants.RATE_LIMITS)

    @property
    def is_connected(self):
        return self._client.open if self._client is not None else False

    @property
    def is_subscribed(self):
        return self._is_subscribed

    # connect to exchange
    async def connect(self):
        extra_headers = self._auth.get_headers() if self._isPrivate else {"User-Agent": Constants.USER_AGENT}
        self._client = await websockets.connect(self._WS_URL, extra_headers=extra_headers)

        return self._client

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
                    raw_msg_str: str = await asyncio.wait_for(self._client.recv(), timeout=Constants.MESSAGE_TIMEOUT)
                    try:
                        msg = json.loads(raw_msg_str)
                        if "ping" in msg:
                            payload = {"op": "pong", "timestamp": str(msg["ping"])}
                            safe_ensure_future(self._client.send(json.dumps(payload)))
                            yield None
                        elif "success" in msg:
                            ws_method: str = msg.get('success', {}).get('message')
                            if ws_method in ['subscribed', 'unsubscribed']:
                                if ws_method == 'subscribed' and len(msg['success']['streams']) > 0:
                                    self._is_subscribed = True
                                    yield None
                                elif ws_method == 'unsubscribed':
                                    self._is_subscribed = False
                                    yield None
                        else:
                            yield msg
                    except ValueError:
                        continue
                except asyncio.TimeoutError:
                    await asyncio.wait_for(self._client.ping(), timeout=Constants.PING_TIMEOUT)
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await self.disconnect()

    # emit messages
    async def _emit(self, method: str, data: Optional[Dict[str, Any]] = {}, no_id: bool = False) -> int:
        async with self._throttler.execute_task(method):
            id = self.generate_request_id()

            payload = {
                "id": id,
                "event": method,
            }

            await self._client.send(json.dumps({**payload, **data}))

            return id

    # request via websocket
    async def request(self, method: str, data: Optional[Dict[str, Any]] = {}) -> int:
        return await self._emit(method, data)

    # subscribe to a method
    async def subscribe(self,
                        streams: Optional[Dict[str, List]] = {}) -> int:
        return await self.request(Constants.WS_EVENT_SUBSCRIBE, {"streams": streams})

    # unsubscribe to a method
    async def unsubscribe(self,
                          streams: Optional[Dict[str, List]] = {}) -> int:
        return await self.request(Constants.WS_EVENT_UNSUBSCRIBE, {"streams": streams})

    # listen to messages by method
    async def on_message(self) -> AsyncIterable[Any]:
        async for msg in self._messages():
            if msg is None:
                yield None
            yield msg
