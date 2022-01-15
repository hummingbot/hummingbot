#!/usr/bin/env python
import asyncio
import logging
import websockets
import ujson
import hummingbot.connector.exchange.btc_markets.btc_markets_constants as constants
from hummingbot.core.utils.async_utils import safe_ensure_future


from typing import Optional, AsyncIterable, Any, List
from websockets.exceptions import ConnectionClosed
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.btc_markets.btc_markets_auth import BtcMarketsAuth
from hummingbot.connector.exchange.btc_markets.btc_markets_utils import RequestId, get_ms_timestamp

# reusable websocket class
# ToDo: We should eventually remove this class, and instantiate web socket connection normally (see Binance for example)


class BtcMarketsWebsocket(RequestId):
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, auth: Optional[BtcMarketsAuth] = None):
        self._auth: Optional[BtcMarketsAuth] = auth
        self._isPrivate = True if self._auth is not None else False
        self._WS_URL = constants.WSS_PRIVATE_URL if self._isPrivate else constants.WSS_PUBLIC_URL
        self._client: Optional[websockets.WebSocketClientProtocol] = None

    # connect to exchange
    async def connect(self):
        try:
            self._client = await websockets.connect(self._WS_URL)

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
                    if "method" in raw_msg and raw_msg["method"] == "heartbeat":
                        payload = {"id": raw_msg["id"], "method": "respond-heartbeat"}
                        safe_ensure_future(self._client.send(ujson.dumps(payload)))
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
    async def _emit(self, method: str, data: Optional[Any] = {}) -> int:
        id = self.generate_request_id()
        nonce = get_ms_timestamp()

        payload = {
            'id': id,
            'messageType': method,
            'timestamp': nonce
        }

        if self._isPrivate:
            auth = self._auth.generate_auth_dict_ws(nonce=nonce)
            payload['signature'] = auth
            payload['key'] = self._auth.api_key

        payload.update(data)

        await self._client.send(ujson.dumps(payload))

        return id

    # request via websocket
    async def request(self, method: str, data: Optional[Any] = {}) -> int:
        return await self._emit(method, data)

    # subscribe to marketIds (plural)
    async def subscribe_marketIds(self, channels: List[str], marketids: List[str]) -> int:
        return await self.request("subscribe", {
            "channels": channels, "marketIds": marketids
        })

    # subscribe to marketId (singular)
    async def subscribe_marketId(self, channels: List[str], marketid: List[str]) -> int:
        return await self.request("subscribe", {
            "channels": channels, "marketId": marketid
        })

    # unsubscribe to a method
    async def unsubscribe(self, channels: List[str]) -> int:
        return await self.request("unsubscribe", {
            "channels": channels
        })

    # listen to messages by method
    async def on_message(self) -> AsyncIterable[Any]:
        async for msg in self._messages():
            yield msg
