#!/usr/bin/env python
import json

import aiohttp
import asyncio
import logging

import hummingbot.connector.exchange.mexc.mexc_constants as CONSTANTS
import hummingbot.connector.exchange.mexc.mexc_utils as mexc_utils

from typing import Dict, Optional, AsyncIterable, Any, List

from hummingbot.connector.exchange.mexc.mexc_auth import MexcAuth
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.logger import HummingbotLogger


class MexcWebSocketAdaptor:

    DEAL_CHANNEL_ID = "push.deal"
    DEPTH_CHANNEL_ID = "push.depth"
    SUBSCRIPTION_LIST = set([DEAL_CHANNEL_ID, DEPTH_CHANNEL_ID])

    _ID_FIELD_NAME = "id"

    _logger: Optional[HummingbotLogger] = None

    MESSAGE_TIMEOUT = 120.0
    PING_TIMEOUT = 10.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(
            self,
            throttler: AsyncThrottler,
            auth: Optional[MexcAuth] = None,
            shared_client: Optional[aiohttp.ClientSession] = None,
    ):

        self._auth: Optional[MexcAuth] = auth
        self._is_private = True if self._auth is not None else False
        self._WS_URL = CONSTANTS.MEXC_WS_URL_PUBLIC
        self._shared_client = shared_client
        self._websocket: Optional[aiohttp.ClientWebSocketResponse] = None
        self._throttler = throttler

    def get_shared_client(self) -> aiohttp.ClientSession:
        if not self._shared_client:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def send_request(self, payload: Dict[str, Any]):
        await self._websocket.send_json(payload)

    async def send_request_str(self, payload: str):
        await self._websocket.send_str(payload)

    async def subscribe_to_order_book_streams(self, trading_pairs: List[str]):
        try:
            for trading_pair in trading_pairs:
                trading_pair = mexc_utils.convert_to_exchange_trading_pair(trading_pair)
                subscribe_deal_request: Dict[str, Any] = {
                    "op": "sub.deal",
                    "symbol": trading_pair,
                }
                async with self._throttler.execute_task(CONSTANTS.MEXC_WS_URL_PUBLIC):
                    await self.send_request_str(json.dumps(subscribe_deal_request))
                subscribe_depth_request: Dict[str, Any] = {
                    "op": "sub.depth",
                    "symbol": trading_pair,
                }
                async with self._throttler.execute_task(CONSTANTS.MEXC_WS_URL_PUBLIC):
                    await self.send_request_str(json.dumps(subscribe_depth_request))

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...", exc_info=True
            )
            raise

    async def subscribe_to_user_streams(self):
        pass

    async def authenticate(self):
        pass

    async def connect(self):
        try:
            self._websocket = await self.get_shared_client().ws_connect(
                url=self._WS_URL)

        except Exception as e:
            self.logger().error(f"Websocket error: '{str(e)}'", exc_info=True)
            raise

    # disconnect from exchange
    async def disconnect(self):
        if self._websocket is None:
            return
        await self._websocket.close()

    async def iter_messages(self) -> AsyncIterable[Any]:
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(self._websocket.receive(), timeout=self.MESSAGE_TIMEOUT)
                    if msg.type == aiohttp.WSMsgType.CLOSED:
                        raise ConnectionError
                    yield json.loads(msg.data)
                except asyncio.TimeoutError:
                    pong_waiter = self._websocket.ping()
                    self.logger().warning("WebSocket receive_json timeout ...")
                    await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
        except ConnectionError:
            return
