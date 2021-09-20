#!/usr/bin/env python
import logging
import json
import time

import aiohttp

from hummingbot.connector.exchange.gate_io import gate_io_constants as CONSTANTS


from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional,
)
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.gate_io.gate_io_auth import GateIoAuth
from hummingbot.connector.exchange.gate_io.gate_io_utils import (
    GateIoAPIError,
)


class GateIoWebsocket:
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 auth: Optional[GateIoAuth] = None):
        self._auth: Optional[GateIoAuth] = auth
        self._is_private = True if self._auth is not None else False
        self._WS_URL = CONSTANTS.WS_URL
        self._session = aiohttp.ClientSession()
        self._client: Optional[aiohttp.ClientWebSocketResponse] = None
        self._closed = True

    # connect to exchange
    async def connect(self):
        self._client = await self._session.ws_connect(
            self._WS_URL, autoping=True, heartbeat=CONSTANTS.MESSAGE_TIMEOUT
        )
        self._closed = False
        return self._client

    # disconnect from exchange
    async def disconnect(self):
        if self._client is None:
            return
        self._closed = True
        await self._client.close()
        self._client = None

    # receive & parse messages
    async def _messages(self) -> AsyncIterable[Any]:
        try:
            while True:
                try:
                    msg = await self._client.receive()
                    if msg.type == aiohttp.WSMsgType.CLOSED:  # happens on ping-pong timeout or ws.close()
                        raise ConnectionError

                    data = json.loads(msg.data)
                    # Raise API error for login failures.
                    if data.get('error', None) is not None:
                        err_msg = data.get('error', {}).get('message', data['error'])
                        raise GateIoAPIError(
                            {'label': 'WSS_ERROR', 'message': f'Error received via websocket - {err_msg}.'}
                        )

                    # Filter subscribed/unsubscribed messages
                    msg_event = data.get('event')
                    if msg_event in ['subscribe', 'unsubscribe']:
                        continue
                    else:
                        yield data

                except ValueError:
                    continue
        except ConnectionError:
            if not self._closed:
                self.logger().warning('The websocket connection was unexpectedly closed.')
            return
        finally:
            await self.disconnect()

    # emit messages
    async def _emit(self, channel: str, data: Optional[Dict[str, Any]] = None, no_id: bool = False) -> int:
        data = data or {}
        payload = {
            'time': int(time.time()),
            'channel': channel,
            **data,
        }

        # if auth class was passed into websocket class
        # we need to emit authenticated requests
        if self._is_private:
            payload['auth'] = self._auth.generate_auth_dict_ws(payload)

        await self._client.send_json(payload)

        return payload['time']

    # request via websocket
    async def request(self, channel: str, data: Optional[Dict[str, Any]] = None) -> int:
        data = data or {}
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
