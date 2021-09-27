#!/usr/bin/env python
from decimal import Decimal

import aiohttp
import asyncio
import time

import logging

from typing import (
    Optional,
    AsyncIterable, Any, Dict,
)

from hummingbot.connector.exchange.peatio.peatio_auth import PeatioAuth
from hummingbot.connector.exchange.peatio.peatio_urls import PEATIO_WS_URL
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger


# PEATIO_ACCOUNT_UPDATE_TOPIC = "accounts.update#2"
PEATIO_ORDER_UPDATE_TOPIC = "orders"

PEATIO_SUBSCRIBE_TOPICS = {
    PEATIO_ORDER_UPDATE_TOPIC,
    # PEATIO_ACCOUNT_UPDATE_TOPIC
}


class PeatioWsChanel(UserStreamTrackerDataSource):
    _hausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._hausds_logger is None:
            cls._hausds_logger = logging.getLogger(__name__)

        return cls._hausds_logger

    def __init__(self, peatio_auth: PeatioAuth):
        self._current_listen_key = None
        self._current_endpoint = None
        self._listen_for_user_steam_task = None
        self._last_recv_time: float = 0
        self._auth: PeatioAuth = peatio_auth
        self._client_session: aiohttp.ClientSession = None
        self._websocket_connection: aiohttp.ClientWebSocketResponse = None
        super().__init__()

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def _send_msg(self, event: str, data: Dict[str, Any]):
        subscribe_request: Dict[str, Any] = {
            # "streams": data,
            "data": data,
            "event": event
        }
        await self._websocket_connection.send_json(subscribe_request)
        self._last_recv_time = time.time()

    async def get_ws_connection(self) -> aiohttp.client._WSRequestContextManager:
        if self._client_session is None:
            self._client_session = aiohttp.ClientSession(headers=self._auth.add_auth_data())

        stream_url: str = f"{PEATIO_WS_URL}?cancel_on_close=1"
        return self._client_session.ws_connect(stream_url, autoclose=False)

    async def _socket_user_stream(self) -> AsyncIterable[str]:
        """
        Main iterator that manages the websocket connection.
        """
        while True:
            try:
                raw_msg = await asyncio.wait_for(self._websocket_connection.receive(), timeout=30)
                self._last_recv_time = time.time()

                if raw_msg.type != aiohttp.WSMsgType.TEXT:
                    # since all ws messages from Peatio are TEXT, any other type should cause ws to reconnect
                    return

                message = raw_msg.json()

                yield message
            except asyncio.TimeoutError:
                self.logger().error("Userstream websocket timeout, going to reconnect...")
                return

    async def create_order(self, market: str, side: str, volume: Decimal, ord_type: str, price: Decimal):
        try:
            # Initialize Websocket Connection
            async with (await self.get_ws_connection()) as ws:
                self._websocket_connection = ws

                data = {
                    "market": market,
                    "side": side,
                    "volume": str(volume),
                    "ord_type": ord_type,
                    "price": str(price)
                }
                await self._send_msg(event="order", data=data)
                # await self._subscribe_topic(PEATIO_ACCOUNT_UPDATE_TOPIC)

                # Listen to WebSocket Connection
                async for message in self._socket_user_stream():
                    return message

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
