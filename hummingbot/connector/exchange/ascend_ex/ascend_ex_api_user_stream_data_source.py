import asyncio
import logging
import time
from typing import List, Optional

import aiohttp

from hummingbot.connector.exchange.ascend_ex import ascend_ex_constants as CONSTANTS
from hummingbot.connector.exchange.ascend_ex.ascend_ex_auth import AscendExAuth
from hummingbot.connector.exchange.ascend_ex.ascend_ex_utils import build_api_factory, get_ws_url_private
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, RESTResponse, WSJSONRequest
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class AscendExAPIUserStreamDataSource(UserStreamTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 15.0
    HEARTBEAT_PING_INTERVAL = 15.0
    PING_TOPIC_ID = "ping"

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(
            self, ascend_ex_auth: AscendExAuth,
            api_factory: Optional[WebAssistantsFactory] = None,
            throttler: Optional[AsyncThrottler] = None,
            trading_pairs: Optional[List[str]] = None
    ):
        super().__init__()
        self._ascend_ex_auth: AscendExAuth = ascend_ex_auth
        self._throttler = throttler or self._get_throttler_instance()
        self._api_factory = api_factory or build_api_factory(throttler=throttler, auth=self._ascend_ex_auth)
        self._rest_assistant: Optional[RESTAssistant] = None
        self._ws_assistant: Optional[WSAssistant] = None
        self._trading_pairs = trading_pairs or []
        self._current_listen_key = None
        self._listen_for_user_stream_task = None

    @property
    def last_recv_time(self) -> float:
        """
        Returns the time of the last received message
        :return: the timestamp of the last received message in seconds
        """
        if self._ws_assistant:
            return self._ws_assistant.last_recv_time
        return 0

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages

        :param output: an async queue where the incoming messages are stored
        """

        ws = None
        while True:
            try:
                rest_assistant = await self._api_factory.get_rest_assistant()
                url = f"{CONSTANTS.REST_URL}/{CONSTANTS.INFO_PATH_URL}"
                request = RESTRequest(method=RESTMethod.GET,
                                      url=url,
                                      endpoint_url=CONSTANTS.INFO_PATH_URL,
                                      is_auth_required=True)

                async with self._throttler.execute_task(CONSTANTS.INFO_PATH_URL):
                    response: RESTResponse = await rest_assistant.call(request=request)

                info = await response.json()
                accountGroup = info.get("data").get("accountGroup")
                headers = self._ascend_ex_auth.get_auth_headers(CONSTANTS.STREAM_PATH_URL)
                payload = {
                    "op": CONSTANTS.SUB_ENDPOINT_NAME,
                    "ch": "order:cash"
                }

                ws: WSAssistant = await self._get_ws_assistant()
                url = f"{get_ws_url_private(accountGroup)}/{CONSTANTS.STREAM_PATH_URL}"
                await ws.connect(ws_url=url, ws_headers=headers, ping_timeout=self.HEARTBEAT_PING_INTERVAL)

                subscribe_request: WSJSONRequest = WSJSONRequest(payload)
                async with self._throttler.execute_task(CONSTANTS.SUB_ENDPOINT_NAME):
                    await ws.send(subscribe_request)

                async for raw_msg in ws.iter_messages():
                    msg = raw_msg.data
                    if msg is None:
                        continue
                    event_type = msg.get("m")
                    if event_type in [self.PING_TOPIC_ID]:
                        await self._handle_ping_message(ws)
                    self._last_recv_time = time.time()
                    output.put_nowait(msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error with AscendEx WebSocket connection. " "Retrying after 30 seconds...",
                    exc_info=True
                )
            finally:
                ws and await ws.disconnect()
                await self._sleep(30.0)

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        return throttler

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def _handle_ping_message(self, ws: aiohttp.ClientWebSocketResponse):
        """
        Responds with pong to a ping message send by a server to keep a websocket connection alive
        """
        async with self._throttler.execute_task(CONSTANTS.PONG_ENDPOINT_NAME):
            payload = {
                "op": "pong"
            }
            pong_request: WSJSONRequest = WSJSONRequest(payload)
            await ws.send(pong_request)
