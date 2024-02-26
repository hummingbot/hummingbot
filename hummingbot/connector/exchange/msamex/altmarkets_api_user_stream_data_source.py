#!/usr/bin/env python

import time
import asyncio
import logging
from typing import (
    Any,
    AsyncIterable,
    List,
    Optional,
)
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from .msamex_constants import Constants
from .msamex_auth import mSamexAuth
from .msamex_websocket import mSamexWebsocket


class mSamexAPIUserStreamDataSource(UserStreamTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 throttler: AsyncThrottler,
                 msamex_auth: mSamexAuth,
                 trading_pairs: Optional[List[str]] = []):
        self._msamex_auth: mSamexAuth = msamex_auth
        self._trading_pairs = trading_pairs
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._last_recv_time: float = 0
        self._throttler = throttler
        self._ws: mSamexWebsocket = None
        super().__init__()

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    @property
    def is_connected(self):
        return self._ws.is_connected if self._ws is not None else False

    async def _listen_to_orders_trades_balances(self) -> AsyncIterable[Any]:
        """
        Subscribe to active orders via web socket
        """

        try:
            self._ws = mSamexWebsocket(self._msamex_auth, throttler=self._throttler)

            await self._ws.connect()

            await self._ws.subscribe(Constants.WS_SUB["USER_ORDERS_TRADES"])

            async for msg in self._ws.on_message():
                # print(f"user msg: {msg}")
                self._last_recv_time = time.time()
                if msg is not None:
                    yield msg

        except Exception as e:
            raise e
        finally:
            await self._ws.disconnect()
            await asyncio.sleep(5)

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages
        :param output: an async queue where the incoming messages are stored
        """

        while True:
            try:
                async for msg in self._listen_to_orders_trades_balances():
                    output.put_nowait(msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    f"Unexpected error with {Constants.EXCHANGE_NAME} WebSocket connection. "
                    "Retrying after 30 seconds...", exc_info=True)
                await asyncio.sleep(30.0)
