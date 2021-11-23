#!/usr/bin/env python

import asyncio
import logging

from typing import Optional
import hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_utils import build_api_factory

from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_auth import DydxPerpetualAuth
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_order_book import DydxPerpetualOrderBook
from hummingbot.core.web_assistant.connections.data_types import WSRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class DydxPerpetualUserStreamDataSource(UserStreamTrackerDataSource):

    HEARTBEAT_INTERVAL = 30.0  # seconds

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, dydx_auth: DydxPerpetualAuth, api_factory: Optional[WebAssistantsFactory] = None):
        self._dydx_auth: DydxPerpetualAuth = dydx_auth
        self._api_factory: WebAssistantsFactory = api_factory or build_api_factory()
        self._ws_assistant: Optional[WSAssistant] = None
        super().__init__()

    @property
    def order_book_class(self):
        return DydxPerpetualOrderBook

    @property
    def last_recv_time(self):
        if self._ws_assistant:
            return self._ws_assistant.last_recv_time
        return -1

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        ws = None
        while True:
            try:
                self.logger().info(f"Connecting to {CONSTANTS.DYDX_WS_URL}")
                ws: WSAssistant = await self._get_ws_assistant()
                await ws.connect(ws_url=CONSTANTS.DYDX_WS_URL, ping_timeout=self.HEARTBEAT_INTERVAL)

                auth_params = self._dydx_auth.get_ws_auth_params()
                auth_request: WSRequest = WSRequest(auth_params)
                await ws.send(auth_request)
                self.logger().info("Authenticated user stream...")

                async for ws_response in ws.iter_messages():
                    data = ws_response.data
                    if data.get("type", "") in ["subscribed", "channel_data"]:
                        output.put_nowait(data)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with dydx WebSocket connection. "
                                    "Retrying after 30 seconds...", exc_info=True)
            finally:
                # Make sure no background tasks is leaked
                ws and await ws.disconnect()
                await self._sleep(30.0)
