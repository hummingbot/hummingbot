#!/usr/bin/env python
import asyncio
import logging
import time
from typing import Any, AsyncIterable, Dict, List, Optional

from hummingbot.connector.exchange.gate_io import gate_io_constants as CONSTANTS
from hummingbot.connector.exchange.gate_io.gate_io_auth import GateIoAuth
from hummingbot.connector.exchange.gate_io.gate_io_utils import GateIoAPIError, build_gate_io_api_factory
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.connections.data_types import WSRequest, WSResponse
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class GateIoWebsocket:
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 auth: Optional[GateIoAuth] = None,
                 api_factory: Optional[WebAssistantsFactory] = None):
        self._auth: Optional[GateIoAuth] = auth
        self._is_private = True if self._auth is not None else False
        self._api_factory = api_factory or build_gate_io_api_factory()
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
            ws_url=CONSTANTS.WS_URL,
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
        try:
            while True:
                try:
                    msg = await self._get_message()

                    data = msg.data
                    # Raise API error for login failures.
                    if data.get("error", None) is not None:
                        err_msg = data.get("error", {}).get("message", data["error"])
                        raise GateIoAPIError(
                            {"label": "WSS_ERROR", "message": f"Error received via websocket - {err_msg}."}
                        )

                    if data.get("channel") == "spot.pong":
                        continue

                    yield data
                except ValueError:
                    continue
        except ConnectionError:
            if not self._closed:
                self.logger().warning("The websocket connection was unexpectedly closed.")
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
            payload["auth"] = self._auth.generate_auth_dict_ws(payload)

        request = WSRequest(payload)
        await self._ws_assistant.send(request)

        return payload["time"]

    async def request(self, channel: str, data: Optional[Dict[str, Any]] = None) -> int:
        data = data or {}
        return await self._emit(channel, data)

    async def subscribe(self,
                        channel: str,
                        trading_pairs: Optional[List[str]] = None) -> int:
        ws_params = {
            "event": "subscribe",
        }
        if trading_pairs is not None:
            ws_params["payload"] = trading_pairs
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
