#!/usr/bin/env python
import asyncio
import logging
import websockets
import ujson
import hummingbot.market.bitcoin_com.bitcoin_com_constants as constants

from typing import Dict, Optional, AsyncIterable, Any
from websockets.exceptions import ConnectionClosed
from hummingbot.logger import HummingbotLogger

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
        self._events: Dict[str, bool] = {}
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._nonce = 0

    def _get_event(self, name: str):
        return self._events.get(name)

    def _set_event(self, name: str):
        self._events[name] = True

    async def _get_ws(self) -> (websockets.WebSocketClientProtocol):
        if self._ws:
            return self._ws

        try:
            self._ws = await websockets.connect(constants.WSS_URL)
        except Exception as e:
            self.logger().error(f"Websocket error: '{str(e)}'", exc_info=True)
        finally:
            return self._ws

    # receive messages
    async def _messages(self) -> AsyncIterable[Any]:
        try:
            while True:
                try:
                    raw_msg: str = await asyncio.wait_for(self._ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                    msg = ujson.loads(raw_msg)
                    method: str = msg.get("method", None)

                    if method in self._events.keys():
                        yield msg

                except asyncio.TimeoutError:
                    try:
                        pong_waiter = await self._ws.ping()
                        await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
                    except asyncio.TimeoutError:
                        raise
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await self._ws.close()

    # subscribe to a method
    async def subscribe(self, name: str, data):
        self._nonce += 1

        await self._get_ws()
        await self._ws.send(ujson.dumps({
            "method": name,
            "id": self._nonce,
            "params": data
        }))

    # yield only specified method name
    async def on(self, name: str) -> AsyncIterable[Any]:
        self._set_event(name)

        while True:
            try:
                async for msg in self._messages():
                    method: str = msg.get("method", None)

                    if (method == name):
                        yield msg["params"]
            except Exception as e:
                self.logger().error(f"Error reading message '{str(e)}'", exc_info=True)
