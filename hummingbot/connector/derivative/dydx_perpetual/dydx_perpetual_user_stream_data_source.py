import asyncio
import logging
from typing import Any, Dict, Optional

import hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_auth import DydxPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class DydxPerpetualUserStreamDataSource(UserStreamTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, dydx_auth: DydxPerpetualAuth, api_factory: Optional[WebAssistantsFactory]):
        self._dydx_auth: DydxPerpetualAuth = dydx_auth
        self._api_factory: WebAssistantsFactory = api_factory
        self._ws_assistant: Optional[WSAssistant] = None
        super().__init__()

    @property
    def last_recv_time(self):
        if self._ws_assistant:
            return self._ws_assistant.last_recv_time
        return -1

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        pass

    async def _connected_websocket_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self.logger().info(f"Connecting to {CONSTANTS.DYDX_WS_URL}")
            self._ws_assistant = await self._api_factory.get_ws_assistant()
            await self._ws_assistant.connect(ws_url=CONSTANTS.DYDX_WS_URL, ping_timeout=CONSTANTS.HEARTBEAT_INTERVAL)

            auth_params = {
                "type": "subscribe",
                "channel": CONSTANTS.WS_CHANNEL_ACCOUNTS,
                "accountNumber": "0",
            }

            auth_request: WSJSONRequest = WSJSONRequest(payload=auth_params, is_auth_required=True)
            await self._ws_assistant.send(auth_request)
            self.logger().info("Authenticated user stream...")
        return self._ws_assistant

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if event_message.get("type", "") in [CONSTANTS.WS_TYPE_SUBSCRIBED, CONSTANTS.WS_TYPE_CHANNEL_DATA]:
            await super()._process_event_message(event_message=event_message, queue=queue)
