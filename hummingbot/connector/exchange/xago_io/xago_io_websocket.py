#!/usr/bin/env python
import asyncio
import logging
import time
from typing import Any, AsyncIterable, Dict, List, Optional

import aiohttp
import ujson

import hummingbot.connector.exchange.xago_io.xago_io_constants as CONSTANTS
import hummingbot.connector.exchange.xago_io.xago_io_utils as xago_io_utils
from hummingbot.connector.exchange.xago_io.xago_io_auth import XagoIoAuth
from hummingbot.logger import HummingbotLogger


class XagoIoWebsocket:

    HEARTBEAT_INTERVAL = 15.0
    ONE_SEC_DELAY = 1.0

    SNAPSHOT_CHANNEL_ID = CONSTANTS.ORDER_BOOK_SNAPSHOT_STREAM
    DIFF_CHANNEL_ID = CONSTANTS.ORDER_BOOK_DIFF_STREAM
    
    ORDER_CHANNEL_ID = CONSTANTS.ORDER_STREAM
    TRADE_CHANNEL_ID = CONSTANTS.TRADE_STREAM
    BALANCE_CHANNEL_ID = CONSTANTS.BALANCE_STREAM

    ORDERBOOK_SUBSCRIPTION_LIST = set([SNAPSHOT_CHANNEL_ID, DIFF_CHANNEL_ID])
    USER_SUBSCRIPTION_LIST = set([ORDER_CHANNEL_ID, BALANCE_CHANNEL_ID, TRADE_CHANNEL_ID])

    _logger: Optional[HummingbotLogger] = None

    """
    Auxiliary class that works as a wrapper of a low level web socket. It contains the logic to create messages
    with the format expected by Crypto.com API
    """

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, auth: XagoIoAuth, shared_client: Optional[aiohttp.ClientSession] = None):
        self._auth: XagoIoAuth = auth
        self._WS_URL = CONSTANTS.WEBSOCKET_URL
        self._shared_client = shared_client
        self._websocket: Optional[aiohttp.ClientWebSocketResponse] = None
        self._last_recv_time: float = 0

    @property
    def last_recv_time(self) -> float:
        """
        Returns the time of the last received message

        :return: the timestamp of the last received message in seconds
        """
        return self._last_recv_time

    def update_last_recv_time(self):
        self._last_recv_time = time.time()

    def get_shared_client(self) -> aiohttp.ClientSession:
        if not self._shared_client:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _sleep(self, delay: float = 1.0):
        await asyncio.sleep(delay)

    async def send_request(self, payload: Dict[str, Any]):
        await self._websocket.send_json(payload)

    async def subscribe_to_order_book_streams(self, trading_pairs: List[str]):
        try:
            for pair in trading_pairs:
                for channel in self.ORDERBOOK_SUBSCRIPTION_LIST:
                    subscription_payload = {
                        "type": "subscribe",
                        "event": f"{channel}.{xago_io_utils.convert_to_exchange_trading_pair(pair)}"
                    }
                    await self.send_request(subscription_payload)

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...", exc_info=True
            )
            raise

    async def subscribe_to_user_streams(self):
        try:
            for channel in self.USER_SUBSCRIPTION_LIST:
                subscription_payload = {
                    "type": "subscribe",
                    "event": channel
                }
                await self.send_request(subscription_payload)
            self.logger().info("Successfully subscribed to user stream...")

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Unexpected error occurred subscribing to user streams...", exc_info=True)
            raise

    async def connect(self):
        try:
            headers = self._auth.get_headers(True)
            self._websocket = await self.get_shared_client().ws_connect(
                url=self._WS_URL,
                heartbeat=self.HEARTBEAT_INTERVAL,
                headers=headers
            )

            await self._sleep(self.ONE_SEC_DELAY)

            self.logger().info("Successfully connected to WebSocket...")

        except Exception as e:
            self.logger().error(f"Websocket error: '{str(e)}'", exc_info=True)
            raise

    # disconnect from exchange
    async def disconnect(self):
        if self._websocket is None:
            return

        await self._websocket.close()

    async def iter_messages(self) -> AsyncIterable[Any]:
        while True:
            try:
                raw_msg = await self._websocket.receive()
                if raw_msg.type == aiohttp.WSMsgType.TEXT:
                    yield ujson.loads(raw_msg.data)
                elif raw_msg.type == aiohttp.WSMsgType.CLOSED:
                    break
                elif raw_msg.type == aiohttp.WSMsgType.ERROR:
                    raise raw_msg.data
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Error parsing websocket message: {str(e)}", exc_info=True)

    async def send_ping(self):
        while True:
            try:
                await self._websocket.ping()
                await self._sleep(self.HEARTBEAT_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Error sending ping: {str(e)}", exc_info=True)
                break
