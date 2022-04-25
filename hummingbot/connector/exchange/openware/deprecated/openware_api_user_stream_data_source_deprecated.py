#!/usr/bin/env python

import hashlib
import hmac
import time
import asyncio
from abc import ABC

# import aiohttp
import logging
from typing import (
    AsyncIterable,
    Dict,
    Optional
)
import ujson
import websockets
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
# from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger


class OpenwareAPIUserStreamDataSourceDeprecated(UserStreamTrackerDataSource, ABC):
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _bausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bausds_logger is None:
            cls._bausds_logger = logging.getLogger(__name__)
        return cls._bausds_logger

    def __init__(self):
        self._header = None
        self._openware_api_url = global_config_map.get("openware_api_url").value
        self._openware_ranger_url = global_config_map.get("openware_ranger_url").value
        timestamp = str(time.time() * 1000)
        self._openware_api_key = global_config_map.get("openware_api_key").value
        self._openware_api_secret = global_config_map.get("openware_api_secret").value
        signature = self._generate_signature(timestamp)
        self._private_header = {
            'X-Auth-Apikey': self._openware_api_key,
            'X-Auth-Nonce': timestamp,
            'X-Auth-Signature': signature
        }
        super().__init__()

    def _generate_signature(self, timestamp):
        query_string = "%s%s" % (timestamp, self._openware_api_key)
        m = hmac.new(self._openware_api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256)
        return m.hexdigest()

    async def _inner_messages(self, ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        try:
            while True:
                yield await ws.recv()
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().warning("Message recv() failed. Going to reconnect...", exc_info=True)
            return

    async def messages(self) -> AsyncIterable[str]:
        try:
            async with (await self.get_ws_connection()) as ws:
                async for msg in self._inner_messages(ws):
                    yield msg
        except asyncio.CancelledError:
            return

    async def get_ws_connection(self) -> websockets.WebSocketClientProtocol:
        stream_url: str = f"{self._openware_ranger_url}/private?stream=trade&stream=order"
        self.logger().info(f"Reconnecting to {stream_url}.")

        # Create the WS connection.
        return websockets.connect(stream_url, header=self._header)

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages
        :param output: an async queue where the incoming messages are stored
        """
        while True:
            try:
                await self.wait_til_next_tick(seconds=60.0)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error while maintaining the user event listen key. Retrying after "
                                    "5 seconds...", exc_info=True)
                await asyncio.sleep(5)

    async def log_user_stream(self, output: asyncio.Queue):
        while True:
            try:
                async for message in self.messages():
                    decoded: Dict[str, any] = ujson.loads(message)
                    output.put_nowait(decoded)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error. Retrying after 5 seconds...", exc_info=True)
                await asyncio.sleep(5.0)

    @staticmethod
    async def wait_til_next_tick(seconds: float = 1.0):
        now: float = time.time()
        current_tick: int = int(now // seconds)
        delay_til_next_tick: float = (current_tick + 1) * seconds - now
        await asyncio.sleep(delay_til_next_tick)
