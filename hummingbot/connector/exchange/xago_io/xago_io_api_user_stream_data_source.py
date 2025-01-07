#!/usr/bin/env python
import asyncio
import logging

from typing import Optional

from hummingbot.connector.exchange.xago_io import (
    xago_io_constants as CONSTANTS,
)
from hummingbot.connector.exchange.xago_io.xago_io_auth import XagoIoAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

class XagoIoAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: XagoIoAuth,
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DOMAIN):
        super().__init__()
        self._auth: XagoIoAuth = auth
        self._current_listen_key = None
        self._domain = domain
        self._api_factory = api_factory
        self._listen_key_initialized_event: asyncio.Event = asyncio.Event()
        self._last_listen_key_ping_ts = 0
        self._last_ws_message_sent_timestamp = 0
        
        self.USER_SUBSCRIPTION_LIST = [
            CONSTANTS.ORDER_STREAM,
            CONSTANTS.TRADE_STREAM,
            CONSTANTS.BALANCE_STREAM
        ]

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange
        """

        ws: WSAssistant = await self._get_ws_assistant()
        url = CONSTANTS.WEBSOCKET_URL
        headers = self._auth.get_headers(True)
        await ws.connect(ws_url=url, ws_headers=headers)
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.


        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """
        try:
            for channel in self.USER_SUBSCRIPTION_LIST:
                subscription_payload = {
                    "type": "subscribe",
                    "event": channel
                }
                request = WSJSONRequest(payload=subscription_payload)
                await websocket_assistant.send(request=request)
                self.logger().info("Successfully subscribed to {} stream...".format(channel))

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().error("Unexpected error occurred subscribing to user streams...", exc_info=True)
            raise

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        await super()._on_user_stream_interruption(websocket_assistant=websocket_assistant)
        await self._sleep(5)
