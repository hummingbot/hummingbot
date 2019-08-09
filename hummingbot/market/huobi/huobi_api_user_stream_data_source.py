#!/usr/bin/env python

import asyncio
import aiohttp
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
                        auth_request = {"op": "auth"}
                        auth_params: Dict[str, any] = self._huobi_auth.generate_auth_dict("get",
                                                                                           "wss://api.huobi.pro",
                                                                                           "/ws/v1",
                                                                                           None)
                        auth_request.update(auth_params)
                        await ws.send(ujson.dumps(auth_request))
                        subscribe_request: Dict[str, any] = {
                            "op": "sub",
                            "topic": f"orders.{item}",
                        }
                        await ws.send(ujson.dumps(subscribe_request))

                    async for raw_msg in self._inner_messages(ws):
                        ws_result = str(zlib.decompressobj(31).decompress(raw_msg), encoding="utf-8")
                        msg: Dict[str, any] = ujson.loads(ws_result)
                        if "err-code" in msg and msg["err-code"] != 0:
                            raise ValueError(f"Huobi Websocket received error message - {msg['err-msg']}")
                        if msg["op"] == "ping":
                            pong_data = {"op": "pong", "ts": msg["ts"]}
                            await ws.send(ujson.dumps(pong_data))
                        elif msg["op"] in ["notify", "req"]:
                            output.put_nowait(msg["data"])
                        elif msg["op"] in ["sub", "unsub", "auth"]:
                            pass
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
