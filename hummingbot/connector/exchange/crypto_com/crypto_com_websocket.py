#!/usr/bin/env python
import aiohttp
import asyncio
import copy
import logging
import ujson
import hummingbot.connector.exchange.crypto_com.crypto_com_constants as constants
from hummingbot.core.utils.async_utils import safe_ensure_future


from typing import Dict, Optional, AsyncIterable, Any, List
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.crypto_com.crypto_com_auth import CryptoComAuth
from hummingbot.connector.exchange.crypto_com.crypto_com_utils import RequestId, get_ms_timestamp

# reusable websocket class
# ToDo: We should eventually remove this class, and instantiate web socket connection normally (see Binance for example)


class CryptoComWebsocket(RequestId):
    HEARTBEAT_INTERVAL = 15.0
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, auth: Optional[CryptoComAuth] = None):
        self._auth: Optional[CryptoComAuth] = auth
        self._isPrivate = True if self._auth is not None else False
        self._WS_URL = constants.WSS_PRIVATE_URL if self._isPrivate else constants.WSS_PUBLIC_URL
        self._client: Optional[aiohttp.ClientWebSocketResponse] = None

    # connect to exchange
    async def connect(self):
        try:
            self._client = await aiohttp.ClientSession().ws_connect(self._WS_URL, heartbeat=self.HEARTBEAT_INTERVAL)

            # if auth class was passed into websocket class
            # we need to emit authenticated requests
            if self._isPrivate:
                await self._emit("public/auth", None)
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

    def _is_ping_message(self, msg: Dict[str, Any]) -> bool:
        return "method" in msg and msg["method"] == "public/heartbeat"

    def _pong(self, ping_msg: Dict[str, Any]):
        ping_id: int = ping_msg["id"]
        pong_payload = {"id": ping_id, "method": "public/respond-heartbeat"}
        safe_ensure_future(self._client.send_json(pong_payload))

    # receive & parse messages
    async def _messages(self) -> AsyncIterable[Any]:
        async for raw_msg in self._client:
            raw_msg = ujson.loads(raw_msg.data)
            if self._is_ping_message(raw_msg):
                self._pong(raw_msg)
                continue
            yield raw_msg

    # emit messages
    async def _emit(self, method: str, data: Optional[Any] = {}) -> int:
        id = self.generate_request_id()
        nonce = get_ms_timestamp()

        payload = {
            "id": id,
            "method": method,
            "nonce": nonce,
            "params": copy.deepcopy(data),
        }

        if self._isPrivate:
            auth = self._auth.generate_auth_dict(
                method,
                request_id=id,
                nonce=nonce,
                data=data,
            )

            payload["sig"] = auth["sig"]
            payload["api_key"] = auth["api_key"]

        await self._client.send_json(payload)

        return id

    # request via websocket
    async def request(self, method: str, data: Optional[Any] = {}) -> int:
        return await self._emit(method, data)

    # subscribe to a method
    async def subscribe(self, channels: List[str]) -> int:
        return await self.request("subscribe", {"channels": channels})

    # unsubscribe to a method
    async def unsubscribe(self, channels: List[str]) -> int:
        return await self.request("unsubscribe", {"channels": channels})

    # listen to messages by method
    async def on_message(self) -> AsyncIterable[Any]:
        async for msg in self._messages():
            yield msg
