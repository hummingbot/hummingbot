import asyncio
import logging
import time
from json import JSONDecodeError
from typing import Any, Dict, Mapping, Optional

import aiohttp

from hummingbot.core.web_assistant.connections.data_types import WSRequest, WSResponse
from hummingbot.logger import HummingbotLogger

s_logger = None


class WSConnection:
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self, aiohttp_client_session: aiohttp.ClientSession):
        self._ping_timeout = None
        self._ws_headers = None
        self._ws_url = None
        self._client_session = aiohttp_client_session
        self._connection: Optional[aiohttp.ClientWebSocketResponse] = None
        self._connected = False
        self._message_timeout: Optional[float] = None
        self._last_recv_time = 0

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(
            self,
            ws_url: str,
            ping_timeout: float = 10,
            message_timeout: Optional[float] = None,
            ws_headers: Optional[Dict] = {},
    ):
        self._ensure_not_connected()
        self._ws_url = ws_url
        self._ws_headers = ws_headers
        self._ping_timeout = ping_timeout
        self._connection = await self._client_session.ws_connect(
            ws_url,
            headers=ws_headers,
            autoping=False,
            heartbeat=ping_timeout,
        )
        self._message_timeout = message_timeout
        self._connected = True

    async def disconnect(self):
        if self._connection is not None and not self._connection.closed:
            await self._connection.close()
        self._connection = None
        self._connected = False

    async def send(self, request: WSRequest):
        self._ensure_connected()
        await request.send_with_connection(connection=self)

    async def ping(self):
        await self._connection.ping()

    async def receive(self) -> Optional[WSResponse]:
        self._ensure_connected()
        response = None
        while self._connected:
            msg = await self._read_message()
            msg = await self._process_message(msg)
            if msg is not None:
                response = self._build_resp(msg)
                break
        return response

    def _ensure_not_connected(self):
        if self._connected:
            raise RuntimeError("WS is connected.")

    def _ensure_connected(self):
        if not self._connected:
            raise RuntimeError("WS is not connected.")

    async def _read_message(self) -> aiohttp.WSMessage:
        try:
            while True:
                try:
                    msg = await self._connection.receive(self._message_timeout)
                    return msg
                except asyncio.TimeoutError:
                    # We timed-out, but is the connection even alive? Ping-Pong
                    await self._connection.ping()
                    await self._connection.receive(self._ping_timeout)

        # The ping timeout exceeded or various type of errors, let's just try to reconnect
        except (asyncio.TimeoutError, asyncio.CancelledError, aiohttp.WebSocketError, aiohttp.ClientError):
            # self.logger().warning("WebSocket reception and ping test timed out. Going to reconnect...")
            return aiohttp.WSMessage(type=aiohttp.WSMsgType.CLOSED, data=None)

    async def _process_message(self, msg: aiohttp.WSMessage) -> Optional[aiohttp.WSMessage]:
        msg = await self._check_msg_types(msg)
        self._update_last_recv_time(msg)
        return msg

    async def _check_msg_types(self, msg: aiohttp.WSMessage) -> Optional[aiohttp.WSMessage]:
        msg = await self._check_msg_closed_type(msg)
        msg = await self._check_msg_ping_type(msg)
        msg = await self._check_msg_pong_type(msg)
        return msg

    async def _check_msg_closed_type(self, msg: Optional[aiohttp.WSMessage]) -> Optional[aiohttp.WSMessage]:
        if msg is not None and msg.type in [aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSE]:
            if self._connected:
                close_code = self._connection.close_code
                self.logger().warning(
                    "The WS connection was closed unexpectedly, attempting to reconnect. "
                    f"Close code = {close_code} msg data: {msg.data}"
                )
                await self.disconnect()
                self._connected = False
                # Attempting to reconnect
                await self.connect(self._ws_url, self._ping_timeout, self._message_timeout, self._ws_headers)
                # raise ConnectionError(
                #    f"The WS connection was closed unexpectedly. Close code = {close_code} msg data: {msg.data}"
                # )
            msg = None
        return msg

    async def _check_msg_ping_type(self, msg: Optional[aiohttp.WSMessage]) -> Optional[aiohttp.WSMessage]:
        if msg is not None and msg.type == aiohttp.WSMsgType.PING:
            await self._connection.pong()
            msg = None
        return msg

    async def _check_msg_pong_type(self, msg: Optional[aiohttp.WSMessage]) -> Optional[aiohttp.WSMessage]:
        if msg is not None and msg.type == aiohttp.WSMsgType.PONG:
            msg = None
        return msg

    def _update_last_recv_time(self, _: aiohttp.WSMessage):
        self._last_recv_time = time.time()

    async def _send_json(self, payload: Mapping[str, Any]):
        await self._connection.send_json(payload)

    async def _send_plain_text(self, payload: str):
        await self._connection.send_str(payload)

    @staticmethod
    def _build_resp(msg: aiohttp.WSMessage) -> WSResponse:
        if msg.type == aiohttp.WSMsgType.BINARY:
            data = msg.data
        else:
            try:
                data = msg.json()
            except JSONDecodeError:
                data = msg.data
        response = WSResponse(data)
        return response
