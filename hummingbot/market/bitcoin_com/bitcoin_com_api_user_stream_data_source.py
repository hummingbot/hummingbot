#!/usr/bin/env python

import asyncio
import logging
import pandas as pd
import time

from typing import Optional, List, AsyncIterable, Any
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.market.bitcoin_com.bitcoin_com_auth import BitcoinComAuth
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.market.bitcoin_com.bitcoin_com_order_book import BitcoinComOrderBook
from hummingbot.market.bitcoin_com.bitcoin_com_websocket import BitcoinComWebsocket
from hummingbot.market.bitcoin_com.bitcoin_com_utils import add_event_type, EventTypes


class BitcoinComAPIUserStreamDataSource(UserStreamTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 30.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, bitcoin_com_auth: BitcoinComAuth, trading_pairs: Optional[List[str]] = []):
        self._bitcoin_com_auth: BitcoinComAuth = bitcoin_com_auth
        self._trading_pairs = trading_pairs
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._last_recv_time: float = 0
        super().__init__()

    @property
    def order_book_class(self):
        """
        *required
        Get relevant order book class to access class specific methods
        :returns: OrderBook class
        """
        return BitcoinComOrderBook

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def _listen_to_reports(self) -> AsyncIterable[Any]:
        """
        Subscribe to reports via web socket
        """

        try:
            ws = BitcoinComWebsocket()
            await ws.connect()

            async for _ in ws.authenticate(self._bitcoin_com_auth.api_key, self._bitcoin_com_auth.secret_key):
                await ws.subscribe("subscribeReports", {})

                async for msg in ws._messages():
                    self._last_recv_time = time.time()

                    if (msg["method"] not in ["activeOrders", "report"]):
                        continue

                    yield msg
        except Exception as e:
            raise e
        finally:
            await ws.disconnect()

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """

        while True:
            try:
                async for response in self._listen_to_reports():
                    if (response["error"] is not None):
                        self.logger().error(response["error"])
                        continue

                    method = response["method"]
                    data = response["data"]

                    if (method == "activeOrders"):
                        for order in data:
                            order_timestamp: float = pd.Timestamp(order["updatedAt"]).timestamp()
                            order_book_message: OrderBookMessage = self.order_book_class.diff_message_from_exchange(
                                add_event_type(EventTypes.ActiveOrdersUpdate, order),
                                order_timestamp
                            )
                            output.put_nowait(order_book_message)
                    else:
                        order_timestamp: float = pd.Timestamp(data["updatedAt"]).timestamp()
                        order_book_message: OrderBookMessage = self.order_book_class.diff_message_from_exchange(
                            add_event_type(EventTypes.ActiveOrdersUpdate, data),
                            order_timestamp
                        )
                        output.put_nowait(order_book_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error with BitcoinCom WebSocket connection. " "Retrying after 30 seconds...", exc_info=True
                )
                await asyncio.sleep(30.0)
