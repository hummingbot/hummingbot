import asyncio
import json
import logging
import time
from typing import Optional, List

import ujson
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.core.data_type.user_stream_tracker_data_source import \
    UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.market.bitfinex.bitfinex_order_book import BitfinexOrderBook
from hummingbot.market.bitfinex import BITFINEX_WS_URI
from hummingbot.market.bitfinex.bitfinex_auth import BitfinexAuth
from hummingbot.market.bitfinex.bitfinex_order_book_message import \
    BitfinexOrderBookMessage


class BitfinexAPIUserStreamDataSource(UserStreamTrackerDataSource):
    MESSAGE_TIMEOUT = 30.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, bitfinex_auth: BitfinexAuth, trading_pairs: Optional[List[str]] = None):
        if trading_pairs is None:
            trading_pairs = []
        self._bitfinex_auth: BitfinexAuth = bitfinex_auth
        self._trading_pairs = trading_pairs
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._last_recv_time: float = 0
        super().__init__()

    @property
    def order_book_class(self):
        return BitfinexOrderBook

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                ws: websockets.WebSocketClientProtocol
                async with websockets.connect(BITFINEX_WS_URI) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    payload = self._bitfinex_auth.generate_auth_payload()
                    await ws.send(json.dumps(payload))

                    async for raw_msg in self._get_response(ws):
                        transformed_msg: BitfinexOrderBookMessage = self._transform_message_from_exchange(raw_msg)
                        if transformed_msg:
                            output.put_nowait(transformed_msg)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error with Bitfinex WebSocket connection. " "Retrying after 30 seconds...",
                    exc_info=True,
                )
                await asyncio.sleep(self.MESSAGE_TIMEOUT)

    def _transform_message_from_exchange(self, raw_msg) -> Optional[BitfinexOrderBookMessage]:
        msg = ujson.loads(raw_msg)
        order_book_message: BitfinexOrderBookMessage = BitfinexOrderBook.diff_message_from_exchange(msg, time.time())
        if any([
            order_book_message.type_heartbeat,
            order_book_message.event_auth,
            order_book_message.event_info,
        ]):
            # skip unneeded events and types
            return
        return order_book_message

    async def _get_response(self, ws: websockets.WebSocketClientProtocol):
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(ws.recv(), timeout=self.MESSAGE_TIMEOUT)
                    self._last_recv_time = time.time()
                    yield msg
                except asyncio.TimeoutError:
                    raise
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await ws.close()
