#!/usr/bin/env python

import time
import asyncio
import logging
from typing import Optional, List, AsyncIterable, Any
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from .btc_markets_auth import BtcMarketsAuth
from .btc_markets_websocket import BtcMarketsWebsocket


class BtcMarketsAPIUserStreamDataSource(UserStreamTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 30.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, btc_markets_auth: BtcMarketsAuth, trading_pairs: Optional[List[str]] = []):
        self._btc_markets_auth: BtcMarketsAuth = btc_markets_auth
        self._ws: BtcMarketsWebsocket = None
        self._trading_pairs = trading_pairs
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._last_recv_time: float = 0
        super().__init__()

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def _listen_to_orders_trades_balances(self) -> AsyncIterable[Any]:
        """
        Subscribe to WebSocket private events to get life cycle of your orders
        https://api.btcmarkets.net/doc/v3#tag/WS_Private_Events
        """

        try:
            ws = BtcMarketsWebsocket(self._btc_markets_auth)
            await ws.connect()
            # subscribe to heartbeat in order to ensure user stream initialises
            await ws.subscribe_marketIds(["orderChange", "heartbeat"], self._trading_pairs)
            async for msg in ws.on_message():
                self.logger().debug(f"WS_SOCKET: {msg}")
                yield msg
                self._last_recv_time = time.time()
                if (msg.get("result") is None):
                    continue
        except Exception as e:
            raise e
        finally:
            await ws.disconnect()
            await asyncio.sleep(5)

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue) -> AsyncIterable[Any]:
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
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
                    "Unexpected error with BtcMarkets WebSocket connection. " "Retrying after 30 seconds...", exc_info=True
                )
                await asyncio.sleep(30.0)
