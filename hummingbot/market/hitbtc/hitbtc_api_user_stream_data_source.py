#!/usr/bin/env python

import asyncio
import aiohttp
import logging
from typing import (
    AsyncIterable,
    Dict,
    Optional,
    Any
)
import time
import ujson
import websockets
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.market.hitbtc.hitbtc_auth import HitBTCAuth
from hummingbot.market.hitbtc.hitbtc_order_book import HitBTCOrderBook
from hummingbot.market.hitbtc.hitbtc_websocket import HitBTCWebsocket

MESSAGE_TIMEOUT = 3.0
PING_TIMEOUT = 5.0


class HitBTCAPIUserStreamDataSource(UserStreamTrackerDataSource):

    _hbausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._hbausds_logger is None:
            cls._hbausds_logger = logging.getLogger(__name__)
        return cls._hbausds_logger

    def __init__(self, hitbtc_auth: HitBTCAuth):
        self._hitbtc_auth: HitBTCAuth = hitbtc_auth
        self._current_auth_token: Optional[str] = None
        self._last_recv_time: float = 0

        super().__init__()

    @property
    def order_book_class(self):
        return HitBTCOrderBook

    @property
    def last_recv_time(self):
        return self._last_recv_time

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                ws = HitBTCWebsocket()

                await ws.login(self._hitbtc_auth)
                await ws.subscribe("subscribeReports", {})

                async for msg in ws.on("report"):
                    self._last_recv_time = time.time()

                    output.put_nowait(msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with HitBTC WebSocket connection. "
                                    "Retrying after 30 seconds...", exc_info=True)
                self._current_auth_token = None
                await asyncio.sleep(30.0)
