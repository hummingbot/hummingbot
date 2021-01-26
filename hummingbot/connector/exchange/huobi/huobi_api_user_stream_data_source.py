#!/usr/bin/env python
import aiohttp
import asyncio
import time

import logging

from typing import (
    Optional,
    AsyncIterable,
    Dict,
    Any,
)

from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.huobi.huobi_auth import HuobiAuth

HUOBI_API_ENDPOINT = "https://api.huobi.pro"
HUOBI_WS_ENDPOINT = "wss://api.huobi.pro/ws/v2"

HUOBI_ACCOUNT_UPDATE_TOPIC = "accounts.update#2"
HUOBI_ORDER_UPDATE_TOPIC = "orders#*"

HUOBI_SUBSCRIBE_TOPICS = {
    HUOBI_ORDER_UPDATE_TOPIC,
    HUOBI_ACCOUNT_UPDATE_TOPIC
}


class HuobiAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _hausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._hausds_logger is None:
            cls._hausds_logger = logging.getLogger(__name__)

        return cls._hausds_logger

    def __init__(self, huobi_auth: HuobiAuth):
        self._current_listen_key = None
        self._current_endpoint = None
        self._listen_for_user_steam_task = None
        self._last_recv_time: float = 0
        self._auth: HuobiAuth = huobi_auth
        self._client_session: aiohttp.ClientSession = None
        self._websocket_connection: aiohttp.ClientWebSocketResponse = None
        super().__init__()

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def _authenticate_client(self):
        """
        Sends an Authentication request to Huobi's WebSocket API Server
        """
        signed_params = self._auth.add_auth_to_params(method="get",
                                                      path_url="/ws/v2",
                                                      is_ws=True
                                                      )
        auth_request: Dict[str: Any] = {
            "action": "req",
            "ch": "auth",
            "params": {
                "authType": "api",
                "accessKey": signed_params["accessKey"],
                "signatureMethod": signed_params["signatureMethod"],
                "signatureVersion": signed_params["signatureVersion"],
                "timestamp": signed_params["timestamp"],
                "signature": signed_params["signature"]
            }
        }
        await self._websocket_connection.send_json(auth_request)
        resp: aiohttp.WSMessage = await self._websocket_connection.receive()
        msg = resp.json()
        if msg.get("code", 0) == 200:
            self.logger().info("Successfully authenticated")

    async def _subscribe_topic(self, topic: str):
        subscribe_request = {
            "action": "sub",
            "ch": topic
        }
        await self._websocket_connection.send_json(subscribe_request)
        self._last_recv_time = time.time()

    async def get_ws_connection(self) -> aiohttp.client._WSRequestContextManager:
        if self._client_session is None:
            self._client_session = aiohttp.ClientSession()

        stream_url: str = f"{HUOBI_WS_ENDPOINT}"
        return self._client_session.ws_connect(stream_url)

    async def _socket_user_stream(self) -> AsyncIterable[str]:
        """
        Main iterator that manages the websocket connection.
        """
        while True:
            try:
                raw_msg = await asyncio.wait_for(self._websocket_connection.receive(), timeout=30)
                self._last_recv_time = time.time()

                if raw_msg.type != aiohttp.WSMsgType.TEXT:
                    # since all ws messages from huobi are TEXT, any other type should cause ws to reconnect
                    return

                message = raw_msg.json()

                # Handle ping messages
                if message["action"] == "ping":
                    pong_response = {
                        "action": "pong",
                        "data": message["data"]
                    }
                    await self._websocket_connection.send_json(pong_response)
                    continue

                yield message
            except asyncio.TimeoutError:
                self.logger().error("Userstream websocket timeout, going to reconnect...")
                return

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                # Initialize Websocket Connection
                async with (await self.get_ws_connection()) as ws:
                    self._websocket_connection = ws

                    # Authentication
                    await self._authenticate_client()

                    # Subscribe to Topic(s)
                    await self._subscribe_topic(HUOBI_ORDER_UPDATE_TOPIC)
                    await self._subscribe_topic(HUOBI_ACCOUNT_UPDATE_TOPIC)

                    # Listen to WebSocket Connection
                    async for message in self._socket_user_stream():
                        output.put_nowait(message)

            except asyncio.CancelledError:
                raise
            except IOError as e:
                self.logger().error(e, exc_info=True)
            except Exception as e:
                self.logger().error(f"Unexpected error occurred! {e} {message}", exc_info=True)
            finally:
                if self._websocket_connection is not None:
                    await self._websocket_connection.close()
                    self._websocket_connection = None
                if self._client_session is not None:
                    await self._client_session.close()
                    self._client_session = None
