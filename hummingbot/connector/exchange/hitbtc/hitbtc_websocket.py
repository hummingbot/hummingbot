#!/usr/bin/env python
import asyncio
import copy
import logging
import websockets
import json
from hummingbot.connector.exchange.hitbtc.hitbtc_constants import Constants


from typing import (
    Any,
    AsyncIterable,
    Dict,
    Optional,
)
from websockets.exceptions import ConnectionClosed
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.hitbtc.hitbtc_auth import HitbtcAuth
from hummingbot.connector.exchange.hitbtc.hitbtc_utils import (
    RequestId,
    HitbtcAPIError,
)

# reusable websocket class
# ToDo: We should eventually remove this class, and instantiate web socket connection normally (see Binance for example)


class HitbtcWebsocket(RequestId):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 auth: Optional[HitbtcAuth] = None):
        self._auth: Optional[HitbtcAuth] = auth
        self._isPrivate = True if self._auth is not None else False
        self._WS_URL = Constants.WS_PRIVATE_URL if self._isPrivate else Constants.WS_PUBLIC_URL
        self._client: Optional[websockets.WebSocketClientProtocol] = None

    # connect to exchange
    async def connect(self):
        self._client = await websockets.connect(self._WS_URL)

        # if auth class was passed into websocket class
        # we need to emit authenticated requests
        if self._isPrivate:
            auth_params = self._auth.generate_auth_dict_ws(self.generate_request_id())
            await self._emit("login", auth_params, no_id=True)
            raw_msg_str: str = await asyncio.wait_for(self._client.recv(), timeout=Constants.MESSAGE_TIMEOUT)
            json_msg = json.loads(raw_msg_str)
            if json_msg.get("result") is not True:
                err_msg = json_msg.get('error', {}).get('message')
                raise HitbtcAPIError({"error": f"Failed to authenticate to websocket - {err_msg}."})

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
                        # HitBTC doesn't support ping or heartbeat messages.
                        # Can handle them here if that changes - use `safe_ensure_future`.
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
        id = self.generate_request_id()

        payload = {
            "id": id,
            "method": method,
            "params": copy.deepcopy(data),
        }

        await self._client.send(json.dumps(payload))

        return id

    # request via websocket
    async def request(self, method: str, data: Optional[Dict[str, Any]] = {}) -> int:
        return await self._emit(method, data)

    # subscribe to a method
    async def subscribe(self,
                        channel: str,
                        trading_pair: Optional[str] = None,
                        params: Optional[Dict[str, Any]] = {}) -> int:
        if trading_pair is not None:
            params['symbol'] = trading_pair
        return await self.request(f"subscribe{channel}", params)

    # unsubscribe to a method
    async def unsubscribe(self,
                          channel: str,
                          trading_pair: Optional[str] = None,
                          params: Optional[Dict[str, Any]] = {}) -> int:
        if trading_pair is not None:
            params['symbol'] = trading_pair
        return await self.request(f"unsubscribe{channel}", params)

    # listen to messages by method
    async def on_message(self) -> AsyncIterable[Any]:
        async for msg in self._messages():
            yield msg
