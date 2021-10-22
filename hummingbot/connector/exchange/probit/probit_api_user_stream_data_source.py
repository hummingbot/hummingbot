#!/usr/bin/env python

import asyncio
import logging
import time

import aiohttp
import ujson
from aiohttp import WSMessage, WSMsgType

import hummingbot.connector.exchange.probit.probit_constants as CONSTANTS

from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional,
)

from hummingbot.connector.exchange.probit.probit_auth import ProbitAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger


class ProbitAPIUserStreamDataSource(UserStreamTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 probit_auth: ProbitAuth,
                 trading_pairs: Optional[List[str]] = None,
                 domain: str = "com",
                 shared_client: Optional[aiohttp.ClientSession] = None):
        super().__init__()
        self._shared_client = shared_client or self._get_session_instance()
        self._domain: str = domain
        self._websocket_client: Optional[aiohttp.ClientWebSocketResponse] = None
        self._probit_auth: ProbitAuth = probit_auth
        self._trading_pairs = trading_pairs or []

        self._last_recv_time: float = 0

    @property
    def exchange_name(self) -> str:
        if self._domain == "com":
            return CONSTANTS.EXCHANGE_NAME
        else:
            return f"{CONSTANTS.EXCHANGE_NAME}_{self._domain}"

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    @classmethod
    def _get_session_instance(cls) -> aiohttp.ClientSession:
        session = aiohttp.ClientSession()
        return session

    async def _init_websocket_connection(self) -> aiohttp.ClientWebSocketResponse:
        """
        Initialize WebSocket client for UserStreamDataSource
        """
        try:
            if self._websocket_client is None:
                self._websocket_client = await self._shared_client.ws_connect(
                    CONSTANTS.WSS_URL.format(self._domain),
                    autoping=False,
                    heartbeat=self.PING_TIMEOUT,
                )
        except Exception:
            self.logger().network("Unexpected error occured with ProBit WebSocket Connection")
            raise
        return self._websocket_client

    async def _authenticate(self, ws: aiohttp.ClientWebSocketResponse):
        """
        Authenticates user to websocket
        """
        try:
            auth_payload: Dict[str, Any] = await self._probit_auth.get_ws_auth_payload()
            await ws.send_str(ujson.dumps(auth_payload, escape_forward_slashes=False))
            auth_resp = await ws.receive_json()

            if auth_resp["result"] != "ok":
                self.logger().error(f"Response: {auth_resp}",
                                    exc_info=True)
                raise
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().info("Error occurred when authenticating to user stream. ",
                               exc_info=True)
            raise

    async def _subscribe_to_channels(self, ws: aiohttp.ClientWebSocketResponse):
        """
        Subscribes to Private User Channels
        """
        try:
            for channel in CONSTANTS.WS_PRIVATE_CHANNELS:
                sub_payload = {
                    "type": "subscribe",
                    "channel": channel
                }
                await ws.send_json(sub_payload)

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(f"Error occurred subscribing to {self.exchange_name} private channels. ",
                                exc_info=True)

    async def _iter_messages(self, ws: aiohttp.ClientWebSocketResponse) -> AsyncIterable[str]:
        try:
            while True:
                msg: WSMessage = await ws.receive()
                self._last_recv_time = int(time.time())
                if msg.type == WSMsgType.CLOSED:
                    return
                elif msg.type == WSMsgType.PING:
                    await ws.pong()
                    continue
                yield msg.data
        except Exception:
            self.logger().error("Unexpected error occurred iterating through websocket messages.",
                                exc_info=True)
            raise
        finally:
            await ws.close()

    async def listen_for_user_stream(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """

        while True:
            try:
                ws: aiohttp.ClientWebSocketResponse = await self._init_websocket_connection()
                self.logger().info("Authenticating to User Stream...")
                await self._authenticate(ws)
                self.logger().info("Successfully authenticated to User Stream.")
                await self._subscribe_to_channels(ws)
                self.logger().info("Successfully subscribed to all Private channels.")

                async for msg in self._iter_messages(ws):
                    output.put_nowait(ujson.loads(msg))
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error with Probit WebSocket connection. Retrying after 30 seconds...",
                    exc_info=True
                )
                if self._websocket_client is not None:
                    await self._websocket_client.close()
                    self._websocket_client = None
                await self._sleep(30.0)

    async def _sleep(self, delay: float):
        await asyncio.sleep(delay)
