#!/usr/bin/env python
import asyncio
import logging
import time
from typing import Any, AsyncIterable, Dict, List, Optional

from hummingbot.connector.exchange.kraken import kraken_constants as CONSTANTS
from hummingbot.connector.exchange.kraken.kraken_auth import KrakenAuth
from hummingbot.connector.exchange.kraken.kraken_utils import build_api_factory
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.connections.data_types import WSRequest, WSResponse
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class KrakenWebsocket:
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 auth: Optional[KrakenAuth] = None,
                 api_factory: Optional[WebAssistantsFactory] = None):
        self._auth: Optional[KrakenAuth] = auth
        self._is_private = True if self._auth is not None else False
        self._api_factory = api_factory or build_api_factory()
        self._ws_assistant: Optional[WSAssistant] = None
        self._closed = True

    @property
    def last_recv_time(self) -> float:
        last_recv_time = 0
        if self._ws_assistant is not None:
            last_recv_time = self._ws_assistant.last_recv_time
        return last_recv_time

    async def connect(self):
        self._ws_assistant = await self._api_factory.get_ws_assistant()
        await self._ws_assistant.connect(
            ws_url=CONSTANTS.WS_AUTH_URL,
            ping_timeout=CONSTANTS.PING_TIMEOUT,
            message_timeout=CONSTANTS.MESSAGE_TIMEOUT,
        )
        self._closed = False

    async def disconnect(self):
        self._closed = True
        if self._ws_assistant is not None:
            await self._ws_assistant.disconnect()
            self._ws_assistant = None

    async def _messages(self) -> AsyncIterable[Any]:
        """
        Generator function that returns messages from the web socket stream
        :param ws: current web socket connection
        :returns: message in AsyncIterable format
        """
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                try:
                    msg: WSResponse = await self._get_message()
                    if (("heartbeat" not in msg.data and
                         "systemStatus" not in msg.data and
                         "subscriptionStatus" not in msg.data)):
                        yield msg.data
                except asyncio.TimeoutError:
                    await self.request(channel="spot.ping")
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        finally:
            await self.disconnect()

    async def _get_message(self) -> WSResponse:
        try:
            response = await self._ws_assistant.receive()
        except asyncio.TimeoutError:
            self.logger().debug("Message receive timed out. Sending ping.")
            await self.request(channel="spot.ping")
            response = await self._ws_assistant.receive()
        return response

    async def _emit(self, channel: str, data: Optional[Dict[str, Any]] = None) -> int:
        data = data or {}
        payload = {
            "time": int(time.time()),
            "channel": channel,
            **data,
        }

        # if auth class was passed into websocket class
        # we need to emit authenticated requests
        if self._is_private:
            payload["auth"] = self._auth.generate_auth_dict(uri=channel, data=data)

        request = WSRequest(payload)
        await self._ws_assistant.send(request)

        return payload["time"]

    async def request(self, channel: str, data: Optional[Dict[str, Any]] = None) -> int:
        data = data or {}
        return await self._emit(channel, data)

    async def subscribe(self,
                        channel: str,
                        current_auth_token: str = None) -> int:
        if current_auth_token is not None:
            ws_params = {
                "event": "subscribe",
                "subscription": {
                    "name": channel,
                    "token": current_auth_token
                }
            }
        else:
            ws_params = {
                "event": "subscribe",
                "subscription": {
                    "name": channel
                }
            }

        return await self.request(channel, ws_params)

    async def unsubscribe(self,
                          channel: str,
                          trading_pairs: Optional[List[str]] = None) -> int:
        ws_params = {
            "event": "unsubscribe",
        }
        if trading_pairs is not None:
            ws_params["payload"] = trading_pairs
        return await self.request(channel, ws_params)

    async def on_message(self) -> AsyncIterable[Any]:
        async for msg in self._messages():
            yield msg
