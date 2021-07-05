#!/usr/bin/env python
import asyncio
import logging
import websockets
import json
import time
from hummingbot.connector.exchange.gate_io.gate_io_constants import Constants


from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional,
)
from websockets.exceptions import ConnectionClosed
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.gate_io.gate_io_auth import GateIoAuth
from hummingbot.connector.exchange.gate_io.gate_io_utils import (
    GateIoAPIError,
)

# reusable websocket class
# ToDo: We should eventually remove this class, and instantiate web socket connection normally (see Binance for example)


class GateIoWebsocket():
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 auth: Optional[GateIoAuth] = None):
        self._auth: Optional[GateIoAuth] = auth
        self._isPrivate = True if self._auth is not None else False
        self._WS_URL = Constants.WS_URL
        self._client: Optional[websockets.WebSocketClientProtocol] = None
        self._is_subscribed = False

    @property
    def is_subscribed(self):
        return self._is_subscribed

    # connect to exchange
    async def connect(self):
        self._client = await websockets.connect(self._WS_URL)

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

                        # Raise API error for login failures.
                        if msg.get('error', None) is not None:
                            err_msg = msg.get('error', {}).get('message', msg['error'])
                            raise GateIoAPIError({"label": "WSS_ERROR", "message": f"Error received via websocket - {err_msg}."})

                        # Filter subscribed/unsubscribed messages
                        msg_event = msg.get('event')
                        if msg_event in ['subscribe', 'unsubscribe']:
                            msg_status = msg.get('result', {}).get('status')
                            if msg_event == 'subscribe' and msg_status == 'success':
                                self._is_subscribed = True
                            elif msg_event == 'unsubscribe' and msg_status == 'success':
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
    async def _emit(self, channel: str, data: Optional[Dict[str, Any]] = {}, no_id: bool = False) -> int:
        payload = {
            "time": int(time.time()),
            "channel": channel,
            **data,
        }

        # if auth class was passed into websocket class
        # we need to emit authenticated requests
        if self._isPrivate:
            payload['auth'] = self._auth.generate_auth_dict_ws(payload)

        await self._client.send(json.dumps(payload))

        return payload['time']

    # request via websocket
    async def request(self, channel: str, data: Optional[Dict[str, Any]] = {}) -> int:
        return await self._emit(channel, data)

    # subscribe to a channel
    async def subscribe(self,
                        channel: str,
                        trading_pairs: Optional[List[str]] = None) -> int:
        ws_params = {
            'event': 'subscribe',
        }
        if trading_pairs is not None:
            ws_params['payload'] = trading_pairs
        return await self.request(channel, ws_params)

    # unsubscribe to a channel
    async def unsubscribe(self,
                          channel: str,
                          trading_pairs: Optional[List[str]] = None) -> int:
        ws_params = {
            'event': 'unsubscribe',
        }
        if trading_pairs is not None:
            ws_params['payload'] = trading_pairs
        return await self.request(channel, ws_params)

    # listen to messages by channel
    async def on_message(self) -> AsyncIterable[Any]:
        async for msg in self._messages():
            yield msg
