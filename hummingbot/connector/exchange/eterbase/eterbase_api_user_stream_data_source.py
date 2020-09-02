#!/usr/bin/env python

import asyncio
import logging
from typing import (
    AsyncIterable,
    Dict,
    Optional,
    List
)
import ujson
import websockets
from websockets.exceptions import ConnectionClosed
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.connector.exchange.eterbase.eterbase_auth import EterbaseAuth
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.connector.exchange.eterbase.eterbase_order_book import EterbaseOrderBook
from hummingbot.connector.exchange.eterbase.eterbase_api_order_book_data_source import EterbaseAPIOrderBookDataSource

import hummingbot.connector.exchange.eterbase.eterbase_constants as constants
from hummingbot.connector.exchange.eterbase.eterbase_utils import api_request

MAX_RETRIES = 20
NaN = float("nan")


class EterbaseAPIUserStreamDataSource(UserStreamTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0
    API_CALL_TIMEOUT = 30.0

    _eausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._eausds_logger is None:
            cls._eausds_logger = logging.getLogger(__name__)
        return cls._eausds_logger

    def __init__(self, eterbase_auth: EterbaseAuth, eterbase_account: str, trading_pairs: Optional[List[str]] = []):
        self._eterbase_auth: EterbaseAuth = eterbase_auth
        self._trading_pairs = trading_pairs
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._eterbase_account = eterbase_account
        self._last_recv_time: float = 0
        super().__init__()

    @property
    def order_book_class(self):
        """
        *required
        Get relevant order book class to access class specific methods
        :returns: OrderBook class
        """
        return EterbaseOrderBook

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """
        while True:
            try:
                tp_map_mkrtid: Dict[str, str] = await EterbaseAPIOrderBookDataSource.get_map_market_id()

                mrktIds = []
                for tp in self._trading_pairs:
                    mrktIds.append(tp_map_mkrtid[tp])

                url = await self._get_ws_url()
                async with websockets.connect(url) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    subscribe_request: Dict[str, any] = {
                        "type": "subscribe",
                        "marketIds": mrktIds,
                        "channelId": "my_orders",
                        "accountId": self._eterbase_account
                    }
                    await ws.send(ujson.dumps(subscribe_request))
                    async for raw_msg in self._inner_messages(ws):
                        self.logger().debug(f"websocket raw msg: {raw_msg}")
                        msg = ujson.loads(raw_msg)
                        msg_type: str = msg.get("type", None)
                        if msg_type is None:
                            raise ValueError(f"Eterbase Websocket message does not contain a type - {msg}")
                        elif msg_type == "pong":
                            # keep alive response to ping
                            pass
                        elif msg_type == "error":
                            raise ValueError(f"Eterbase Websocket received error message - {msg['msg']}")
                        elif msg_type in ["o_placed", "o_triggered", "o_fill", "o_closed"]:
                            order_book_message: OrderBookMessage = self.order_book_class.diff_message_from_exchange(msg)
                            output.put_nowait(order_book_message)
                        elif msg_type in ["o_rejected"]:
                            # these messages are not needed to track the order book
                            pass
                        else:
                            raise ValueError(f"Unrecognized Eterbase Websocket message received - {msg}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with Eterbase WebSocket connection. "
                                    "Retrying after 30 seconds...", exc_info=True)
                await asyncio.sleep(30.0)

    async def _inner_messages(self,
                              ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        """
        Generator function that returns messages from the web socket stream
        :param ws: current web socket connection
        :returns: message in AsyncIterable format
        """
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                    yield msg
                except asyncio.TimeoutError:
                    try:
                        await ws.send('{"type": "ping"}')
                    except asyncio.TimeoutError:
                        raise
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await ws.close()

    async def _get_ws_url(self) -> str:
        """
        call get token api to receive token for web socket connection
        """
        resp = await api_request("GET", "/wstoken", auth=self._eterbase_auth)
        wstoken = resp["wstoken"]
        if (wstoken is None):
            raise ValueError(f"Service /api/wstoken didn't received generated wstoken in response: {resp}")
        url = f"{constants.WSS_URL}?wstoken={wstoken}"
        return url

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time
