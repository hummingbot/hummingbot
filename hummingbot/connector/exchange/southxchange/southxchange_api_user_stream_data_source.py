#!/usr/bin/env python
import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, List, Optional

from hummingbot.connector.exchange.southxchange.southxchange_auth import SouthXchangeAuth
from hummingbot.connector.exchange.southxchange.southxchange_constants import PRIVATE_WS_URL, RATE_LIMITS, REST_URL
from hummingbot.connector.exchange.southxchange.southxchange_utils import build_api_factory
from hummingbot.connector.exchange.southxchange.southxchange_web_utils import RESTAssistant_SX, WebAssistantsFactory_SX
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, RESTResponse, WSJSONRequest
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.southxchange.southxchange_exchange import SouthxchangeExchange


class SouthxchangeAPIUserStreamDataSource(UserStreamTrackerDataSource):
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
            self,
            southxchange_auth: SouthXchangeAuth,
            connector: 'SouthxchangeExchange',
            api_factory: Optional[WebAssistantsFactory_SX] = None,
            throttler: Optional[AsyncThrottler] = None,
            trading_pairs: Optional[List[str]] = None,
    ):
        super().__init__()
        self._southxchange_auth: SouthXchangeAuth = southxchange_auth
        self._throttler = throttler or self._get_throttler_instance()
        self._api_factory = api_factory or build_api_factory(throttler=throttler, auth=self._southxchange_auth)
        self._rest_assistant: Optional[RESTAssistant_SX] = None
        self._ws_assistant: Optional[WSAssistant] = None
        self._trading_pairs = trading_pairs or []
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._lock = asyncio.Lock()
        self._connector = connector

    async def listen_for_user_stream(self, output: asyncio.Queue) -> AsyncIterable[Any]:
        """
        *required
        Subscribe to user stream via web socket, and keep the connection open for incoming messages
        :param ev_loop: ev_loop to execute this function in
        :param output: an async queue where the incoming messages are stored
        """
        ws = None
        while True:
            url = f"{REST_URL}GetWebSocketToken"
            try:
                data = await self._connector._api_request(
                    path_url="GetWebSocketToken",
                    method=RESTMethod.POST,
                    is_auth_required=True
                )
            except Exception as exception:
                raise IOError(f"Error fetching user stream listen key. Error: {exception}")
            idMarket = await self._get_market_id(self._trading_pairs)
            try:
                payload = {
                    "k": "subscribe",
                    "v": idMarket
                }
                ws: WSAssistant = await self._get_ws_assistant()
                url = PRIVATE_WS_URL.format(access_token=data)
                await ws.connect(ws_url=url)
                subscribe_request: WSJSONRequest = WSJSONRequest(payload)
                async with self._throttler.execute_task("SXC"):
                    await ws.send(subscribe_request)

                async for raw_msg in ws.iter_messages():
                    msg = raw_msg.data
                    if msg is None:
                        continue
                    self._last_recv_time = time.time()
                    output.put_nowait(msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error with SouthXchange WebSocket connection. " "Retrying after 30 seconds...", exc_info=True
                )
                await asyncio.sleep(60.0)
            finally:
                ws and await ws.disconnect()

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        throttler = AsyncThrottler(RATE_LIMITS)
        return throttler

    async def _get_market_id(cls, trading_pairs: List[str]) -> int:
        throttler = cls._throttler or cls._get_throttler_instance()
        api_factory = cls._api_factory or build_api_factory(throttler=throttler)
        rest_assistant = await api_factory.get_rest_assistant()

        url = f"{REST_URL}/markets"
        request = RESTRequest(method=RESTMethod.GET, url=url)

        try:
            async with throttler.execute_task(limit_id="SXC"):
                response: RESTResponse = await rest_assistant.call(request=request)
                if response.status != 200:
                    return []
                data: Dict[str, Dict[str, Any]] = await response.json()
                for symbol_data in data:
                    if trading_pairs[0] == (f"{symbol_data[0]}-{symbol_data[1]}"):
                        return symbol_data[2]
        except Exception as ex:
            cls.logger().error(f"There was an error requesting exchange info ({str(ex)})")
        return 0
