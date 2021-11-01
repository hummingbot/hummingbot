#!/usr/bin/env python
import asyncio

import logging

from typing import (
    Optional,
    List,
)

from hummingbot.connector.exchange.mexc.constants import (
    MEXC_PING_URL,
)
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.mexc.mexc_auth import MexcAuth

import time


class MexcAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _mexcausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._mexcausds_logger is None:
            cls._mexcausds_logger = logging.getLogger(__name__)

        return cls._mexcausds_logger

    def __init__(self, mexc_auth: MexcAuth, trading_pairs: Optional[List[str]] = []):
        self._current_listen_key = None
        self._current_endpoint = None
        self._listen_for_user_stram_task = None
        self._last_recv_time: float = 0
        self._auth: MexcAuth = mexc_auth
        self._trading_pairs = trading_pairs
        super().__init__()

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def _authenticate_client(self):
        pass
        # await self._websocket_connection.send(json.dumps(self._auth.generate_ws_auth()))
        # resp = await self._websocket_connection.recv()
        # msg = json.loads(resp)
        # if msg["event"] != 'login':
        #     self.logger().error(f"Error occurred authenticating to websocket API server. {msg}")
        # self.logger().info("Successfully authenticated")

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                await self._api_request(method="GET", path_url=MEXC_PING_URL)
                self._last_recv_time = time.time()
                await asyncio.sleep(3.0)
            except Exception as ex:
                self.logger().error(f"Unexpected error occurred! {ex}", exc_info=True)
