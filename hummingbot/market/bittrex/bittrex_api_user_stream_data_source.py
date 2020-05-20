#!/usr/bin/env python

import asyncio
import hashlib
import hmac
import logging
import time
from base64 import b64decode
from typing import AsyncIterable, Dict, Optional, List, Any
from zlib import decompress, MAX_WBITS

import signalr_aio
import ujson
from async_timeout import timeout
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.market.bittrex.bittrex_auth import BittrexAuth
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.market.bittrex.bittrex_order_book import BittrexOrderBook

BITTREX_WS_FEED = "https://socket.bittrex.com/signalr"
MAX_RETRIES = 20
MESSAGE_TIMEOUT = 30.0
NaN = float("nan")


class BittrexAPIUserStreamDataSource(UserStreamTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _btausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._btausds_logger is None:
            cls._btausds_logger = logging.getLogger(__name__)
        return cls._btausds_logger

    def __init__(self, bittrex_auth: BittrexAuth, trading_pairs: Optional[List[str]] = []):
        self._bittrex_auth: BittrexAuth = bittrex_auth
        self._trading_pairs = trading_pairs
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._last_recv_time: float = 0
        self._websocket_connection: Optional[signalr_aio.Connection] = None
        super().__init__()

    @property
    def order_book_class(self):
        return BittrexOrderBook

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def _socket_user_stream(self, conn: signalr_aio.Connection) -> AsyncIterable[str]:
        try:
            while True:
                async with timeout(MESSAGE_TIMEOUT):
                    msg = await conn.msg_queue.get()
                    self._last_recv_time = time.time()
                    yield msg
        except asyncio.TimeoutError:
            self.logger().warning(f"Message recv() timed out. Reconnecting to Bittrex SignalR WebSocket... ")

    def _transform_raw_message(self, msg) -> Dict[str, Any]:

        timestamp_patten = "%Y-%m-%dT%H:%M:%S"

        def _decode_message(raw_message: bytes) -> Dict[str, Any]:
            try:
                decode_msg: bytes = decompress(b64decode(raw_message, validate=True), -MAX_WBITS)
            except SyntaxError:
                decode_msg: bytes = decompress(b64decode(raw_message, validate=True))
            except Exception:
                self.logger().error(f"Error decoding message", exc_info=True)
                return {"error": "Error decoding message"}

            return ujson.loads(decode_msg.decode(), precise_float=True)

        def _is_auth_context(msg):
            return "R" in msg and type(msg["R"]) is not bool and msg["I"] == str(0)

        def _is_order_delta(msg) -> bool:
            return len(msg.get("M", [])) > 0 and type(msg["M"][0]) == dict and msg["M"][0].get("M", None) == "uO"

        def _is_balance_delta(msg) -> bool:
            return len(msg.get("M", [])) > 0 and type(msg["M"][0]) == dict and msg["M"][0].get("M", None) == "uB"

        def _get_signed_challenge(api_secret: str, challenge: str):
            return hmac.new(api_secret.encode(), challenge.encode(), hashlib.sha512).hexdigest()

        output: Dict[str, Any] = {"event_type": None, "content": None, "error": None}
        msg: Dict[str, Any] = ujson.loads(msg)

        if _is_auth_context(msg):
            output["event_type"] = "auth"
            output["content"] = {"signature": _get_signed_challenge(self._bittrex_auth.secret_key, msg["R"])}
        elif _is_balance_delta(msg):
            output["event_type"] = "uB"
            output["content"] = _decode_message(msg["M"][0]["A"][0])
            output["time"] = time.strftime(timestamp_patten, time.gmtime(output["content"]['d']['u'] / 1000))

        elif _is_order_delta(msg):
            output["event_type"] = "uO"
            output["content"] = _decode_message(msg["M"][0]["A"][0])
            output["time"] = time.strftime(timestamp_patten, time.gmtime(output["content"]['o']['u'] / 1000))

            # TODO: Refactor accordingly when V3 WebSocket API is released
            # WebSocket API returns market trading_pairs in 'Quote-Base' format
            # Code below converts 'Quote-Base' -> 'Base-Quote'
            output["content"]["o"].update({
                "E": f"{output['content']['o']['E'].split('-')[1]}-{output['content']['o']['E'].split('-')[0]}"
            })

        return output

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                self._websocket_connection = signalr_aio.Connection(BITTREX_WS_FEED, session=None)
                hub = self._websocket_connection.register_hub("c2")

                self.logger().info("Invoked GetAuthContext")
                hub.server.invoke("GetAuthContext", self._bittrex_auth.api_key)
                self._websocket_connection.start()

                async for raw_message in self._socket_user_stream(self._websocket_connection):
                    decode: Dict[str, Any] = self._transform_raw_message(raw_message)
                    if decode.get("error") is not None:
                        self.logger().error(decode["error"])
                        continue

                    if decode.get("content") is not None:
                        signature = decode["content"].get("signature")
                        content_type = decode["event_type"]
                        if signature is not None:
                            hub.server.invoke("Authenticate", self._bittrex_auth.api_key, signature)
                            continue

                        if content_type in ["uO", "uB"]:  # uB: Balance Delta, uO: Order Delta
                            order_delta: OrderBookMessage = self.order_book_class.diff_message_from_exchange(decode)
                            output.put_nowait(order_delta)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error with Bittrex WebSocket connection. " "Retrying after 30 seconds...", exc_info=True
                )
                await asyncio.sleep(30.0)
