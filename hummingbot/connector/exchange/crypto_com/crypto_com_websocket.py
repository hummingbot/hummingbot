#!/usr/bin/env python
import aiohttp
import asyncio
import logging
import ujson

import hummingbot.connector.exchange.crypto_com.crypto_com_constants as CONSTANTS
import hummingbot.connector.exchange.crypto_com.crypto_com_utils as crypto_com_utils

from typing import Dict, Optional, AsyncIterable, Any, List

from hummingbot.connector.exchange.crypto_com.crypto_com_auth import CryptoComAuth
from hummingbot.connector.exchange.crypto_com.crypto_com_utils import get_ms_timestamp
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.logger import HummingbotLogger


class CryptoComWebsocket:

    AUTH_REQUEST = "public/auth"
    PING_METHOD = "public/heartbeat"
    PONG_METHOD = "public/respond-heartbeat"
    HEARTBEAT_INTERVAL = 15.0
    ONE_SEC_DELAY = 1.0

    DIFF_CHANNEL_ID = "book"
    TRADE_CHANNEL_ID = "trade"
    SUBSCRIPTION_LIST = set([DIFF_CHANNEL_ID, TRADE_CHANNEL_ID])

    _ID_FIELD_NAME = "id"
    _METHOD_FIELD_NAME = "method"
    _NONCE_FIELD_NAME = "nonce"
    _PARAMS_FIELD_NAME = "params"
    _SIGNATURE_FIELD_NAME = "sig"
    _API_KEY_FIELD_NAME = "api_key"

    _SUBSCRIPTION_OPERATION = "subscribe"
    _CHANNEL_PARAMS = "channels"
    _USER_CHANNEL_LIST = ["user.order", "user.trade", "user.balance"]

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

    def __init__(self, auth: Optional[CryptoComAuth] = None, shared_client: Optional[aiohttp.ClientSession] = None):
        self._auth: Optional[CryptoComAuth] = auth
        self._is_private = True if self._auth is not None else False
        self._WS_URL = CONSTANTS.WSS_PRIVATE_URL if self._is_private else CONSTANTS.WSS_PUBLIC_URL
        self._shared_client = shared_client
        self._websocket: Optional[aiohttp.ClientWebSocketResponse] = None

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
            channels = []
            for pair in trading_pairs:
                channels.extend(
                    [
                        f"{self.DIFF_CHANNEL_ID}.{crypto_com_utils.convert_to_exchange_trading_pair(pair)}.150",
                        f"{self.TRADE_CHANNEL_ID}.{crypto_com_utils.convert_to_exchange_trading_pair(pair)}",
                    ]
                )
            subscription_payload = {
                self._ID_FIELD_NAME: get_tracking_nonce(),
                self._METHOD_FIELD_NAME: self._SUBSCRIPTION_OPERATION,
                self._NONCE_FIELD_NAME: get_ms_timestamp(),
                self._PARAMS_FIELD_NAME: {self._CHANNEL_PARAMS: channels},
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
            channels = self._USER_CHANNEL_LIST
            subscription_payload = {
                self._ID_FIELD_NAME: get_tracking_nonce(),
                self._METHOD_FIELD_NAME: self._SUBSCRIPTION_OPERATION,
                self._NONCE_FIELD_NAME: get_ms_timestamp(),
                self._PARAMS_FIELD_NAME: {self._CHANNEL_PARAMS: channels},
            }
            await self.send_request(subscription_payload)

            self.logger().info("Successfully subscribed to user stream...")

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Unexpected error occurred subscribing to user streams...", exc_info=True)
            raise

    async def authenticate(self):
        request_id = get_tracking_nonce()
        nonce = get_ms_timestamp()

        auth = self._auth.generate_auth_dict(
            self.AUTH_REQUEST,
            request_id=request_id,
            nonce=nonce,
        )
        auth_payload = {
            self._ID_FIELD_NAME: request_id,
            self._METHOD_FIELD_NAME: self.AUTH_REQUEST,
            self._NONCE_FIELD_NAME: nonce,
            self._SIGNATURE_FIELD_NAME: auth["sig"],
            self._API_KEY_FIELD_NAME: auth["api_key"],
        }
        await self.send_request(auth_payload)

    async def connect(self):
        try:
            self._websocket = await self.get_shared_client().ws_connect(
                url=self._WS_URL, heartbeat=self.HEARTBEAT_INTERVAL
            )

            # According to Crypto.com API documentation, it is recommended to add a 1 second delay from when the
            # websocket connection is established and when the first request is sent.
            # Ref: https://exchange-docs.crypto.com/spot/index.html#rate-limits
            await self._sleep(self.ONE_SEC_DELAY)

            # if auth class was passed into websocket class
            # we need to emit authenticated requests
            if self._is_private:
                await self.authenticate()
                self.logger().info("Successfully authenticate to user stream...")

        except Exception as e:
            self.logger().error(f"Websocket error: '{str(e)}'", exc_info=True)
            raise

    # disconnect from exchange
    async def disconnect(self):
        if self._websocket is None:
            return

        await self._websocket.close()

    def _is_ping_message(self, msg: Dict[str, Any]) -> bool:
        return "method" in msg and msg["method"] == self.PING_METHOD

    async def _pong(self, ping_msg: Dict[str, Any]):
        ping_id: int = ping_msg["id"]
        pong_payload = {"id": ping_id, "method": self.PONG_METHOD}
        await self.send_request(pong_payload)

    async def iter_messages(self) -> AsyncIterable[Any]:
        while True:
            raw_msg = await self._websocket.receive()
            raw_msg = ujson.loads(raw_msg.data)
            if self._is_ping_message(raw_msg):
                await self._pong(raw_msg)
                continue
            yield raw_msg
