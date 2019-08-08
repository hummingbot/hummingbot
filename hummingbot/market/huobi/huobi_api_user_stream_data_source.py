#!/usr/bin/env python

import asyncio
import logging
from typing import (
    AsyncIterable,
    Dict,
    Optional,
    List
)
import zlib
import ujson
import websockets
from websockets.exceptions import ConnectionClosed
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.market.huobi.huobi_auth import HuobiAuth
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.market.huobi.huobi_order_book import HuobiOrderBook

HUOBI_REST_API = "https://api.huobi.pro"
HUOBI_WS_FEED = "wss://api.huobi.pro/ws/v1"


class HuobiAPIUserStreamDataSource(UserStreamTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _hausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._hausds_logger is None:
            cls._hausds_logger = logging.getLogger(__name__)
        return cls._hausds_logger

    def __init__(self, huobi_auth: HuobiAuth, symbols: Optional[List[str]] = []):
        self._huobi_auth: HuobiAuth = huobi_auth
        self._symbols = symbols
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        super().__init__()

    @property
    def order_book_class(self):
        return HuobiOrderBook

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                async with websockets.connect(HUOBI_WS_FEED) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for item in self._symbols:
                        subscribe_params: Dict[str, any] = {
                            "op": "auth",
                            #"topic": f"orders.{item}",
                        }
                        subscribe_request: Dict[str, any] = self._huobi_auth.generate_auth_dict("get",
                                                                                                "wss://api.huobi.pro",
                                                                                                f"orders.{item}",
                                                                                                subscribe_params)
                        await ws.send(ujson.dumps(subscribe_request))
                    async for raw_msg in self._inner_messages(ws):
                        ws_result = str(zlib.decompressobj(31).decompress(raw_msg), encoding="utf-8")
                        msg: Dict[str, any] = ujson.loads(ws_result)
                        if "err-code" in msg:
                            raise ValueError(f"Huobi Websocket received error message - code {msg['err-code']}")
                        msg_type: str = msg.get("op", None)
                        if msg_type is None:
                            raise ValueError(f"Huobi Websocket message does not contain a type - {msg}")
                        elif msg_type == "notify":
                            output.put_nowait(msg["data"])
                        else:
                            raise ValueError(f"Unrecognized Huobi Websocket message received - {msg}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with Huobi WebSocket connection. "
                                    "Retrying after 30 seconds...", exc_info=True)
                await asyncio.sleep(30.0)

    async def _inner_messages(self,
                              ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
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
