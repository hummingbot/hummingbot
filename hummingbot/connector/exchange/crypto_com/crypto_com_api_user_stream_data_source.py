#!/usr/bin/env python
import aiohttp
import time
import asyncio
import logging

import hummingbot.connector.exchange.crypto_com.crypto_com_constants as CONSTANTS

from typing import Optional, AsyncIterable, Any

from hummingbot.connector.exchange.crypto_com.crypto_com_auth import CryptoComAuth
from hummingbot.connector.exchange.crypto_com.crypto_com_websocket import CryptoComWebsocket
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger


class CryptoComAPIUserStreamDataSource(UserStreamTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 30.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(
        self,
        crypto_com_auth: CryptoComAuth,
        shared_client: Optional[aiohttp.ClientSession] = None,
    ):
        super().__init__()
        self._crypto_com_auth: CryptoComAuth = crypto_com_auth
        self._shared_client = shared_client

        self._last_recv_time: float = 0
        self._auth_successful_event = asyncio.Event()

    @property
    def ready(self) -> bool:
        return self.last_recv_time > 0 and self._auth_successful_event.is_set()

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    def _get_shared_client(self) -> aiohttp.ClientSession:
        """
        Retrieves the shared aiohttp.ClientSession. If no shared client is provided, create a new ClientSession.
        """
        if not self._shared_client:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _create_websocket_connection(self) -> CryptoComWebsocket:
        """
        Initialize sets up the websocket connection with a CryptoComWebsocket object.
        """
        try:
            ws = CryptoComWebsocket(auth=self._crypto_com_auth, shared_client=self._get_shared_client())
            await ws.connect()
            return ws
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(f"Unexpected error occured connecting to {CONSTANTS.EXCHANGE_NAME} WebSocket API. "
                                  f"({e})")
            raise

    async def listen_for_user_stream(self, output: asyncio.Queue) -> AsyncIterable[Any]:
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """
        ws = None
        while True:
            try:
                ws = await self._create_websocket_connection()
                await ws.subscribe_to_user_streams()
                async for msg in ws.iter_messages():
                    self._last_recv_time = time.time()
                    if msg.get("method", "") == CryptoComWebsocket.AUTH_REQUEST and msg.get("code", -1) == 0:
                        self._auth_successful_event.set()
                    if msg.get("result") is None:
                        continue
                    output.put_nowait(msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error when listening to user streams. Retrying after 5 seconds...", exc_info=True
                )
                await self._sleep(5)
            finally:
                ws and await ws.disconnect()
