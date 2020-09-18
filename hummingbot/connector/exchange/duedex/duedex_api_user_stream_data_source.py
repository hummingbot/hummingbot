#!/usr/bin/env python
import aiohttp
import asyncio
import logging
from typing import (
    Optional,
    AsyncIterable,
)

from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.duedex.duedex_auth import DuedexAuth

DUEDEX_WS_URI = "wss://feed.duedex.com/v1/feed"


class DuedexAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _user_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._user_logger is None:
            cls._user_logger = logging.getLogger(__name__)

        return cls._user_logger

    def __init__(self, duedex_auth: DuedexAuth):
        self._current_listen_key = None
        self._current_endpoint = None
        self._listen_for_user_steam_task = None
        self._last_recv_time: float = 0
        self._auth: DuedexAuth = duedex_auth
        self._client_session: aiohttp.ClientSession = None
        self._websocket_connection: aiohttp.ClientWebSocketResponse = None
        super().__init__()

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def _authenticate_client(self):
        """
        To authenticate, the client first sends a challenge message.
        """
        req = {"type": "challenge"}
        await self._websocket_connection.send_json(req)
        resp: aiohttp.WSMessage = await self._websocket_connection.receive()
        msg = resp.json()
        if "type" in msg and msg["type"] == "challenge":
            req = self._auth.get_ws_signature_dict(msg['challenge'])
            await self._websocket_connection.send_json(req)
            resp: aiohttp.WSMessage = await self._websocket_connection.receive()
            msg = resp.json()
            if "type" in msg and msg["type"] == "auth":
                self.logger().info("Successfully authenticated")
                return
        self.logger().error(f"Error occurred authenticating to websocket API server. {msg}")

    async def _subscribe_topic(self, topic: str):
        subscribe_request = {
            "type": "subscribe",
            "channels": [
                {
                    "name": topic,
                }
            ]
        }
        await self._websocket_connection.send_json(subscribe_request)

    async def get_ws_connection(self) -> aiohttp.client._WSRequestContextManager:
        if self._client_session is None:
            self._client_session = aiohttp.ClientSession()

        stream_url: str = f"{DUEDEX_WS_URI}"
        return self._client_session.ws_connect(stream_url)

    async def _socket_user_stream(self) -> AsyncIterable[str]:
        """
        Main iterator that manages the websocket connection.
        """
        while True:
            raw_msg = await self._websocket_connection.receive()

            if raw_msg.type != aiohttp.WSMsgType.TEXT:
                continue

            message = raw_msg.json()
            # import sys
            # print(f"MSG: {message}", file=sys.stdout)
            yield message

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                # Initialize Websocket Connection
                async with (await self.get_ws_connection()) as ws:
                    self._websocket_connection = ws

                    # Authentication
                    await self._authenticate_client()

                    # Subscribe to Topic(s)
                    await self._subscribe_topic("margins")
                    await self._subscribe_topic("orders")
                    # await self._subscribe_topic("executions")

                    # Listen to WebSocket Connection
                    async for message in self._socket_user_stream():
                        if "type" in message:
                            if message["type"] == "subscriptions":
                                self.logger().info(f"Successfully subscribed to {message['channels']}.")
                            else:
                                output.put_nowait(message)

            except asyncio.CancelledError:
                raise
            except IOError as e:
                self.logger().error(e, exc_info=True)
            except Exception as e:
                self.logger().error(f"Unexpected error occurred! {e}", exc_info=True)
            finally:
                if self._websocket_connection is not None:
                    await self._websocket_connection.close()
                    self._websocket_connection = None
                if self._client_session is not None:
                    await self._client_session.close()
                    self._client_session = None
