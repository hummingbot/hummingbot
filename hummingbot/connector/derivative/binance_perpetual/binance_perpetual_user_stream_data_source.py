import asyncio
import logging
import time
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_auth import BinancePerpetualAuth

import hummingbot.connector.derivative.binance_perpetual.constants as CONSTANTS
import hummingbot.connector.derivative.binance_perpetual.binance_perpetual_utils as utils

from typing import (
    Any,
    Dict,
    Optional,
    Tuple,
)

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class BinancePerpetualUserStreamDataSource(UserStreamTrackerDataSource):

    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800  # Recommended to Ping/Update listen key to keep connection alive
    HEARTBEAT_TIME_INTERVAL = 30.0

    _bpusds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bpusds_logger is None:
            cls._bpusds_logger = logging.getLogger(__name__)
        return cls._bpusds_logger

    @property
    def last_recv_time(self) -> float:
        if self._ws_assistant:
            return self._ws_assistant.last_recv_time
        return 0

    def __init__(
        self,
        auth: BinancePerpetualAuth,
        domain: str = "binance_perpetual",
        throttler: Optional[AsyncThrottler] = None,
        api_factory: Optional[WebAssistantsFactory] = None
    ):
        super().__init__()
        self._api_factory: WebAssistantsFactory = api_factory or utils.build_api_factory(auth=auth)
        self._rest_assistant: Optional[RESTAssistant] = None
        self._ws_assistant: Optional[WSAssistant] = None
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._domain = domain
        self._throttler = throttler or self._get_throttler_instance()
        self._last_listen_key_ping_ts = None

        self._manage_listen_key_task = None
        self._listen_key_initialized_event: asyncio.Event = asyncio.Event()

    async def _get_rest_assistant(self) -> RESTAssistant:
        if self._rest_assistant is None:
            self._rest_assistant = await self._api_factory.get_rest_assistant()
        return self._rest_assistant

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        return AsyncThrottler(CONSTANTS.RATE_LIMITS)

    async def get_listen_key(self):
        rest_assistant = await self._get_rest_assistant()

        async with self._throttler.execute_task(limit_id=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT):

            request = RESTRequest(
                method=RESTMethod.POST,
                url=utils.rest_url(CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, self._domain),
                is_auth_required=True,
            )
            response = await rest_assistant.call(request=request)
            data: Dict[str, str] = await response.json()
            if response.status != 200:
                raise IOError(
                    f"Error fetching Binance Perpetual user stream listen key. "
                    f"HTTP status is {response.status}. Error: {data}"
                )
            return data["listenKey"]

    async def ping_listen_key(self) -> bool:
        rest_assistant = await self._get_rest_assistant()

        async with self._throttler.execute_task(limit_id=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT):
            url = utils.rest_url(CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, self._domain)

            request = RESTRequest(
                method=RESTMethod.PUT,
                url=url,
                params={"listenKey": self._current_listen_key}
            )
            response = await rest_assistant.call(request=request)

            data: Tuple[str, Any] = await response.json()
            if "code" in data:
                self.logger().warning(f"Failed to refresh the listen key {self._current_listen_key}: {data}")
                return False
            return True

    async def _manage_listen_key_task_loop(self):
        try:
            while True:
                if self._current_listen_key is None:
                    self._current_listen_key = await self.get_listen_key()
                    self.logger().info(f"Successfully obtained listen key {self._current_listen_key}")
                    self._listen_key_initialized_event.set()
                else:
                    success: bool = await self.ping_listen_key()
                    if not success:
                        self.logger().error("Error occurred renewing listen key... ")
                        break
                    else:
                        self.logger().info(f"Refreshed listen key {self._current_listen_key}.")
                        self._last_listen_key_ping_ts = int(time.time())
                await self._sleep(self.LISTEN_KEY_KEEP_ALIVE_INTERVAL)

        except Exception as e:
            self.logger().error(f"Unexpected error occurred with maintaining listen key. "
                                f"Error {e}")
            raise
        finally:
            self._current_listen_key = None
            self._listen_key_initialized_event.clear()

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        ws = None
        while True:
            try:
                self._manage_listen_key_task = safe_ensure_future(self._manage_listen_key_task_loop())
                await self._listen_key_initialized_event.wait()

                url = f"{utils.wss_url(CONSTANTS.PRIVATE_WS_ENDPOINT, self._domain)}/{self._current_listen_key}"
                ws: WSAssistant = await self._get_ws_assistant()
                await ws.connect(ws_url=url, ping_timeout=self.HEARTBEAT_TIME_INTERVAL)

                async for msg in ws.iter_messages():
                    if len(msg.data) > 0:
                        output.put_nowait(msg.data)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(
                    f"Unexpected error while listening to user stream. Retrying after 5 seconds... "
                    f"Error: {e}",
                    exc_info=True,
                )
            finally:
                # Make sure no background task is leaked.
                ws and await ws.disconnect()
                self._manage_listen_key_task and self._manage_listen_key_task.cancel()
                self._current_listen_key = None
                self._listen_key_initialized_event.clear()
                await self._sleep(5)
