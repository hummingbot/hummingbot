#!/usr/bin/env python
import websockets
import asyncio
import json

import logging

from typing import (
    Optional,
    AsyncIterable,
    List,
    Dict,
    Any
)

from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.okex.okex_auth import OKExAuth

from hummingbot.connector.exchange.okex.constants import OKEX_WS_URI_PRIVATE

import time


class OkexAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _okexausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._okexausds_logger is None:
            cls._okexausds_logger = logging.getLogger(__name__)

        return cls._okexausds_logger

    def __init__(self, okex_auth: OKExAuth, trading_pairs: Optional[List[str]] = []):
        self._current_listen_key = None
        self._current_endpoint = None
        self._listen_for_user_steam_task = None
        self._last_recv_time: float = 0
        self._auth: OKExAuth = okex_auth
        self._trading_pairs = trading_pairs
        self._websocket_connection = None
        super().__init__()

    @property
    def last_recv_time(self) -> float:
        """Should be updated(using python's time.time()) everytime a message is received from the websocket."""
        return self._last_recv_time

    async def _authenticate_client(self):
        """
        Sends an Authentication request to OKEx's WebSocket API Server
        """
        await self._websocket_connection.send(json.dumps(self._auth.generate_ws_auth()))

        resp = await self._websocket_connection.recv()
        msg = json.loads(resp)

        if msg["event"] != 'login':
            self.logger().error(f"Error occurred authenticating to websocket API server. {msg}")

        self.logger().info("Successfully authenticated")

    async def _subscribe_topic(self, topic: Dict[str, Any]):
        subscribe_request = {
            "op": "subscribe",
            "args": topic
        }
        request = json.dumps(subscribe_request)
        await self._websocket_connection.send(request)
        resp = await self._websocket_connection.recv()
        msg = json.loads(resp)
        if msg["event"] != "subscribe":
            self.logger().error(f"Error occurred subscribing to topic. {topic}. {msg}")
        self.logger().info(f"Successfully subscribed to {topic}")

    async def get_ws_connection(self):
        stream_url: str = f"{OKEX_WS_URI_PRIVATE}"
        return websockets.connect(stream_url)

    async def _socket_user_stream(self) -> AsyncIterable[str]:
        """
        Main iterator that manages the websocket connection.
        """
        while True:
            try:
                raw_msg = await asyncio.wait_for(self._websocket_connection.recv(), timeout=20)

                # yield json.loads(inflate(raw_msg))
                yield json.loads(raw_msg)
            except asyncio.TimeoutError:
                try:
                    await self._websocket_connection.send('ping')
                    await asyncio.wait_for(self._websocket_connection.recv(), timeout=5)
                except asyncio.TimeoutError:
                    self.logger().warning("WebSocket ping timed out. Going to reconnect...")
                    return
            except Exception:
                return

    # TODO needs testing, paper mode is not connecting for some reason
    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """Subscribe to user stream via web socket, and keep the connection open for incoming messages"""
        while True:
            try:
                if self._websocket_connection is not None:
                    await self._websocket_connection.close()
                    self._websocket_connection = None
                # Initialize Websocket Connection
                async with (await self.get_ws_connection()) as ws:
                    self._websocket_connection = ws

                    # Authentication
                    await self._authenticate_client()
                    subscription_list = []

                    assets = set()
                    # Subscribe to Topic(s)
                    for trading_pair in self._trading_pairs:
                        # orders
                        subscription_list.append({
                            "channel": "orders",
                            "instType": "SPOT",
                            "instId": trading_pair})

                        # balances
                        source, quote = trading_pair.split('-')
                        assets.add(source)
                        assets.add(quote)

                    # all assets
                    for asset in assets:
                        subscription_list.append({
                            "channel": "account",
                            "ccy": asset})

                    # subscribe to all channels
                    await self._subscribe_topic(subscription_list)

                    # Listen to WebSocket Connection
                    async for message in self._socket_user_stream():
                        self._last_recv_time = time.time()

                        # handle all the messages in the queue
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
