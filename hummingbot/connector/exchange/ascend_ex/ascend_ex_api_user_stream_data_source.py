#!/usr/bin/env python
import time
import asyncio
import logging
import aiohttp
import ujson

from typing import Optional, List, AsyncIterable, Any

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.ascend_ex.ascend_ex_auth import AscendExAuth
from hummingbot.connector.exchange.ascend_ex import ascend_ex_constants as CONSTANTS
from hummingbot.connector.exchange.ascend_ex.ascend_ex_utils import get_ws_url_private


class AscendExAPIUserStreamDataSource(UserStreamTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 10.0
    PING_TIMEOUT = 5.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(
        self, ascend_ex_auth: AscendExAuth, shared_client: Optional[aiohttp.ClientSession] = None, throttler: Optional[AsyncThrottler] = None, trading_pairs: Optional[List[str]] = None
    ):
        super().__init__()
        self._shared_client = shared_client or self._get_session_instance()
        self._throttler = throttler or self._get_throttler_instance()
        self._ascend_ex_auth: AscendExAuth = ascend_ex_auth
        self._trading_pairs = trading_pairs or []
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._last_recv_time: float = 0

    @classmethod
    def _get_session_instance(cls) -> aiohttp.ClientSession:
        session = aiohttp.ClientSession()
        return session

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        return throttler

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue) -> AsyncIterable[Any]:
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """

        while True:
            try:
                headers = {
                    **self._ascend_ex_auth.get_headers(),
                    **self._ascend_ex_auth.get_auth_headers("info"),
                    **self._ascend_ex_auth.get_hb_id_headers(),
                }
                async with self._throttler.execute_task(CONSTANTS.INFO_PATH_URL):
                    response = await self._shared_client.get(
                        f"{CONSTANTS.REST_URL}/{CONSTANTS.INFO_PATH_URL}", headers=headers
                    )
                info = await response.json()
                accountGroup = info.get("data").get("accountGroup")
                headers = {
                    **self._ascend_ex_auth.get_auth_headers("stream"),
                    **self._ascend_ex_auth.get_hb_id_headers(),
                }
                payload = {
                    "op": CONSTANTS.SUB_ENDPOINT_NAME,
                    "ch": "order:cash"
                }

                async with aiohttp.ClientSession().ws_connect(f"{get_ws_url_private(accountGroup)}/stream", headers=headers) as ws:
                    try:
                        async with self._throttler.execute_task(CONSTANTS.SUB_ENDPOINT_NAME):
                            await ws.send_json(payload)

                        async for raw_msg in self._iter_messages(ws):
                            try:
                                msg = ujson.loads(raw_msg)
                                if msg is None:
                                    continue
                                if msg.get("m", '') == "ping":
                                    async with self._throttler.execute_task(CONSTANTS.PONG_ENDPOINT_NAME):
                                        safe_ensure_future(self._handle_ping_message(ws))
                                output.put_nowait(msg)
                            except Exception:
                                self.logger().error(
                                    "Unexpected error when parsing AscendEx message. ", exc_info=True
                                )
                                raise
                    except Exception:
                        self.logger().error(
                            "Unexpected error while listening to AscendEx messages. ", exc_info=True
                        )
                        raise
                    finally:
                        await ws.close()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error with AscendEx WebSocket connection. " "Retrying after 30 seconds...", exc_info=True
                )
                await asyncio.sleep(30.0)

    async def _iter_messages(
        self,
        ws: aiohttp.ClientWebSocketResponse
    ) -> AsyncIterable[str]:
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                raw_msg = await ws.receive()
                if raw_msg.type == aiohttp.WSMsgType.CLOSED:
                    raise ConnectionError
                self._last_recv_time = time.time()
                yield raw_msg.data

        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        finally:
            await ws.close()

    async def _handle_ping_message(self, ws: aiohttp.ClientWebSocketResponse):
        async with self._throttler.execute_task(CONSTANTS.PONG_ENDPOINT_NAME):
            pong_payload = {
                "op": "pong"
            }
            await ws.send_json(pong_payload)
