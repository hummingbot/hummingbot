#!/usr/bin/env python

import time
import asyncio
import logging
# import pandas as pd

from typing import Optional, List, AsyncIterable, Any
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
# from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.market.crypto_com.crypto_com_auth import CryptoComAuth
from hummingbot.market.crypto_com.crypto_com_order_book import CryptoComOrderBook
from hummingbot.market.crypto_com.crypto_com_websocket import CryptoComWebsocket
# from hummingbot.market.crypto_com.crypto_com_utils import add_event_type, EventTypes


class CryptoComAPIUserStreamDataSource(UserStreamTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 30.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, crypto_com_auth: CryptoComAuth, trading_pairs: Optional[List[str]] = []):
        self._crypto_com_auth: CryptoComAuth = crypto_com_auth
        self._trading_pairs = trading_pairs
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._last_recv_time: float = 0
        super().__init__()

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    @property
    def order_book_class(self):
        """
        *required
        Get relevant order book class to access class specific methods
        :returns: OrderBook class
        """
        return CryptoComOrderBook

    async def _listen_to_active_orders(self) -> AsyncIterable[Any]:
        """
        Subscribe to active orders via web socket
        """

        try:
            ws = CryptoComWebsocket(self._crypto_com_auth)
            await ws.connect()
            await ws.subscribe(["user.order"])
            print("_listen_to_active_orders")

            async for msg in ws.onMessage():
                self._last_recv_time = time.time()

                if (msg.get("result") is None):
                    continue

                yield msg
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

        print("listen_for_user_stream")

        while True:
            try:
                async for msg in self._listen_to_active_orders():
                    print("msg", msg)
                    yield msg
                    # update = data["update"]
                    # timestamp: float = pd.Timestamp(update["time"]).timestamp()
                    # order_book_message: OrderBookMessage = self.order_book_class.diff_message_from_exchange(
                    #     add_event_type(EventTypes.ActiveOrdersUpdate, update),
                    #     timestamp
                    # )
                    # output.put_nowait(order_book_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error with CryptoCom WebSocket connection. " "Retrying after 30 seconds...", exc_info=True
                )
                await asyncio.sleep(30.0)
