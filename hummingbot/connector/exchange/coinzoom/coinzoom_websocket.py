#!/usr/bin/env python
import asyncio
import logging
import websockets
import json
from hummingbot.connector.exchange.coinzoom.coinzoom_constants import Constants


from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional,
)
from websockets.exceptions import ConnectionClosed
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.coinzoom.coinzoom_auth import CoinzoomAuth

# reusable websocket class
# ToDo: We should eventually remove this class, and instantiate web socket connection normally (see Binance for example)


class CoinzoomWebsocket():
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 auth: Optional[CoinzoomAuth] = None):
        self._auth: Optional[CoinzoomAuth] = auth
        self._isPrivate = True if self._auth is not None else False
        self._WS_URL = Constants.WS_PRIVATE_URL if self._isPrivate else Constants.WS_PUBLIC_URL
        self._client: Optional[websockets.WebSocketClientProtocol] = None
        self._is_subscribed = False

    @property
    def is_subscribed(self):
        return self._is_subscribed

    # connect to exchange
    async def connect(self):
        # if auth class was passed into websocket class
        # we need to emit authenticated requests
        extra_headers = self._auth.get_headers() if self._isPrivate else {"User-Agent": "hummingbot"}
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

                        # CoinZoom doesn't support ping or heartbeat messages.
                        # Can handle them here if that changes - use `safe_ensure_future`.

                        # Check response for a subscribed/unsubscribed message;
                        result: List[str] = list([d['result']
                                                 for k, d in msg.items()
                                                 if (isinstance(d, dict) and d.get('result') is not None)])

                        if len(result):
                            if result[0] == 'subscribed':
                                self._is_subscribed = True
                            elif result[0] == 'unsubscribed':
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
    async def _emit(self, method: str, action: str, data: Optional[Dict[str, Any]] = {}) -> int:
        payload = {
            method: {
                "action": action,
                **data
            }
        }
        return await self._client.send(json.dumps(payload))

    # request via websocket
    async def request(self, method: str, action: str, data: Optional[Dict[str, Any]] = {}) -> int:
        return await self._emit(method, action, data)

    # subscribe to a method
    async def subscribe(self,
                        streams: Optional[Dict[str, Any]] = {}) -> int:
        for stream, stream_dict in streams.items():
            if self._isPrivate:
                stream_dict = {**stream_dict, **self._auth.get_ws_params()}
            await self.request(stream, "subscribe", stream_dict)
        return True

    # unsubscribe to a method
    async def unsubscribe(self,
                          streams: Optional[Dict[str, Any]] = {}) -> int:
        for stream, stream_dict in streams.items():
            if self._isPrivate:
                stream_dict = {**stream_dict, **self._auth.get_ws_params()}
            await self.request(stream, "unsubscribe", stream_dict)
        return True

    # listen to messages by method
    async def on_message(self) -> AsyncIterable[Any]:
        async for msg in self._messages():
            yield msg
