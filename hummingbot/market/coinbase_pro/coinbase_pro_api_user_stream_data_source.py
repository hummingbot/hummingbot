#!/usr/bin/env python

import asyncio
import logging
from typing import AsyncIterable, Dict, Optional, List
import ujson
import websockets
from websockets.exceptions import ConnectionClosed
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.market.bitroyal.bitroyal_auth import bitroyalAuth
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.market.bitroyal.bitroyal_order_book import bitroyalOrderBook

bitroyal_REST_URL = "https://api.pro.bitroyal.com"
bitroyal_WS_FEED = "wss://ws-feed.pro.bitroyal.com"
MAX_RETRIES = 20
NaN = float("nan")


class bitroyalAPIUserStreamDataSource(UserStreamTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _cbpausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._cbpausds_logger is None:
            cls._cbpausds_logger = logging.getLogger(__name__)
        return cls._cbpausds_logger

    def __init__(self, bitroyal_auth: bitroyalAuth, symbols: Optional[List[str]] = []):
        self._bitroyal_auth: bitroyalAuth = bitroyal_auth
        self._symbols = symbols
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        super().__init__()

    @property
    def order_book_class(self):
<<<<<<< HEAD:hummingbot/market/coinbase_pro/coinbase_pro_api_user_stream_data_source.py
        """
        *required
        Get relevant order book class to access class specific methods
        :returns: OrderBook class
        """
        return CoinbaseProOrderBook
=======
        return bitroyalOrderBook
>>>>>>> resolved conflict in settings.py:hummingbot/market/bitroyal/bitroyal_api_user_stream_data_source.py

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """
        while True:
            try:
                async with websockets.connect(bitroyal_WS_FEED) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    subscribe_request: Dict[str, any] = {
                        "type": "subscribe",
                        "product_ids": self._symbols,
                        "channels": ["user"],
                    }
                    auth_dict: Dict[str] = self._bitroyal_auth.generate_auth_dict("get", "/users/self/verify", "")
                    subscribe_request.update(auth_dict)
                    await ws.send(ujson.dumps(subscribe_request))
                    async for raw_msg in self._inner_messages(ws):
                        msg = ujson.loads(raw_msg)
                        msg_type: str = msg.get("type", None)
                        if msg_type is None:
                            raise ValueError(f"bitroyal Pro Websocket message does not contain a type - {msg}")
                        elif msg_type == "error":
                            raise ValueError(f"bitroyal Pro Websocket received error message - {msg['message']}")
                        elif msg_type in ["open", "match", "change", "done"]:
                            order_book_message: OrderBookMessage = self.order_book_class.diff_message_from_exchange(msg)
                            output.put_nowait(order_book_message)
                        elif msg_type in ["received", "activate", "subscriptions"]:
                            # these messages are not needed to track the order book
                            pass
                        else:
                            raise ValueError(f"Unrecognized bitroyal Pro Websocket message received - {msg}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error with bitroyal Pro WebSocket connection. " "Retrying after 30 seconds...",
                    exc_info=True,
                )
                await asyncio.sleep(30.0)

<<<<<<< HEAD:hummingbot/market/coinbase_pro/coinbase_pro_api_user_stream_data_source.py
    async def _inner_messages(self,
                              ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        """
        Generator function that returns messages from the web socket stream
        :param ws: current web socket connection
        :returns: message in AsyncIterable format
        """
=======
    async def _inner_messages(self, ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
>>>>>>> resolved conflict in settings.py:hummingbot/market/bitroyal/bitroyal_api_user_stream_data_source.py
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                    yield msg
                except asyncio.TimeoutError:
                    try:
                        pong_waiter = await ws.ping()
                        await asyncio.wait_for(pong_waiter, timeout=self.PING_TIMEOUT)
                    except asyncio.TimeoutError:
                        raise
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await ws.close()
