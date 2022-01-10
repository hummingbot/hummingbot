import asyncio
import hashlib
import hmac
import logging
import time
import uuid

from base64 import b64decode
from typing import Any, AsyncIterable, Dict, List, Optional
from zlib import decompress, MAX_WBITS

import signalr_aio
import ujson

from async_timeout import timeout

from hummingbot.connector.exchange.bittrex.bittrex_auth import BittrexAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger

BITTREX_WS_FEED = "https://socket-v3.bittrex.com/signalr"
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
        self._hub = None
        super().__init__()

    @property
    def hub(self):
        return self._hub

    @hub.setter
    def hub(self, value):
        self._hub = value

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
            self.logger().warning("Message recv() timed out. Reconnecting to Bittrex SignalR WebSocket... ")

    def _transform_raw_message(self, msg) -> Dict[str, Any]:

        def _decode_message(raw_message: bytes) -> Dict[str, Any]:
            try:
                decode_msg: bytes = decompress(b64decode(raw_message, validate=True), -MAX_WBITS)
            except SyntaxError:
                decode_msg: bytes = decompress(b64decode(raw_message, validate=True))
            except Exception:
                self.logger().error("Error decoding message", exc_info=True)
                return {"error": "Error decoding message"}

            return ujson.loads(decode_msg.decode(), precise_float=True)

        def _is_event_type(msg, event_name) -> bool:
            return len(msg.get("M", [])) > 0 and type(msg["M"][0]) == dict and msg["M"][0].get("M", None) == event_name

        def _is_heartbeat(msg):
            return _is_event_type(msg, "heartbeat")

        def _is_auth_notification(msg):
            return _is_event_type(msg, "authenticationExpiring")

        def _is_order_delta(msg) -> bool:
            return _is_event_type(msg, "order")

        def _is_balance_delta(msg) -> bool:
            return _is_event_type(msg, "balance")

        def _is_execution_event(msg) -> bool:
            return _is_event_type(msg, "execution")

        output: Dict[str, Any] = {"event_type": None, "content": None, "error": None}
        msg: Dict[str, Any] = ujson.loads(msg)

        if _is_auth_notification(msg):
            output["event_type"] = "re-authenticate"

        elif _is_heartbeat(msg):
            output["event_type"] = "heartbeat"

        elif _is_balance_delta(msg) or _is_order_delta(msg) or _is_execution_event(msg):
            output["event_type"] = msg["M"][0]["M"]
            output["content"] = _decode_message(msg["M"][0]["A"][0])

        return output

    async def listen_for_user_stream(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        while True:
            try:
                self._websocket_connection = signalr_aio.Connection(BITTREX_WS_FEED, session=None)
                self.hub = self._websocket_connection.register_hub("c3")

                await self.authenticate()
                self.hub.server.invoke("Subscribe", ["heartbeat", "order", "balance", "execution"])
                self._websocket_connection.start()

                async for raw_message in self._socket_user_stream(self._websocket_connection):
                    decode: Dict[str, Any] = self._transform_raw_message(raw_message)
                    self.logger().debug(f"Got ws message {decode}")
                    if decode.get("error") is not None:
                        self.logger().error(decode["error"])
                        continue

                    content_type = decode.get("event_type")
                    if content_type is not None:
                        if content_type in ["balance", "order", "execution"]:
                            output.put_nowait(decode)
                        elif content_type == "re-authenticate":
                            await self.authenticate()
                        elif content_type == "heartbeat":
                            self.logger().debug("WS heartbeat")
                            continue

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error with Bittrex WebSocket connection. " "Retrying after 30 seconds...", exc_info=True
                )
                await asyncio.sleep(30.0)

    async def authenticate(self):
        self.logger().info("Authenticating...")
        timestamp = int(round(time.time() * 1000))
        randomized = str(uuid.uuid4())
        challenge = f"{timestamp}{randomized}"
        signed_challenge = hmac.new(self._bittrex_auth.secret_key.encode(), challenge.encode(), hashlib.sha512).hexdigest()
        self.hub.server.invoke("Authenticate", self._bittrex_auth.api_key, timestamp, randomized, signed_challenge)
        return
