import asyncio
import json
import logging
from typing import Any, Dict, Optional

from hummingbot.connector.exchange.vest import vest_constants as CONSTANTS
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class VestAPIUserStreamDataSource(UserStreamTrackerDataSource):

    MESSAGE_TIMEOUT = 30.0
    PING_TIMEOUT = 10.0

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: AuthBase,
                 connector,
                 api_factory: WebAssistantsFactory):
        super().__init__()
        self._auth: AuthBase = auth
        self._connector = connector
        self._api_factory: WebAssistantsFactory = api_factory

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Create an authenticated WebSocket connection for user stream data
        """
        ws_url = CONSTANTS.get_vest_ws_url(self._connector.vest_environment)
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=ws_url, ping_timeout=self.PING_TIMEOUT)

        # Authenticate the WebSocket connection
        auth_payload = self._auth.websocket_login_parameters()
        login_request = WSJSONRequest(payload=auth_payload)
        await ws.send(login_request)

        # Wait for authentication response
        response = await ws.receive()

        # Parse response data
        try:
            if isinstance(response.data, bytes):
                response_data = json.loads(response.data.decode('utf-8'))
            elif isinstance(response.data, str):
                response_data = json.loads(response.data)
            else:
                response_data = response.data
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise Exception(f"Failed to parse WebSocket authentication response: {e}")

        if response_data.get("result", {}).get("status") != "authenticated":
            raise Exception(f"Failed to authenticate WebSocket connection: {response_data}")

        return ws

    async def _subscribe_channels(self, websocket: WSAssistant):
        """
        Subscribe to user stream channels (account updates, order updates)
        """
        try:
            # Subscribe to account updates
            payload = {
                "method": "SUBSCRIBE",
                "params": [CONSTANTS.VEST_WS_ACCOUNT_CHANNEL],
                "id": 1
            }
            subscribe_request = WSJSONRequest(payload=payload)
            await websocket.send(subscribe_request)

            self.logger().info("Subscribed to user stream channels")
        except Exception as e:
            self.logger().error(f"Failed to subscribe to user stream channels: {e}")
            raise

    async def _process_websocket_messages(self, websocket: WSAssistant):
        """
        Process incoming user stream WebSocket messages
        """
        try:
            async for ws_response in websocket.iter_messages():
                data = ws_response.data
                if self._is_user_stream_message(data):
                    yield data
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error processing user stream messages")
            raise

    def _is_user_stream_message(self, message: Dict[str, Any]) -> bool:
        """
        Check if message is a user stream message
        """
        return (
            message.get("stream") == CONSTANTS.VEST_WS_ACCOUNT_CHANNEL or
            "account" in message or
            "order" in message
        )
