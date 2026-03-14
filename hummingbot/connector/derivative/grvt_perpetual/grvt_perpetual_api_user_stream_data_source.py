import asyncio
import time
from typing import TYPE_CHECKING, Optional

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_auth import GRVTPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_derivative import (
        GRVTPerpetualDerivative,
    )


class GRVTPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    """
    User stream data source for GRVT Perpetual.
    Handles WebSocket connections for user-specific data like orders and positions.
    """
    HEARTBEAT_TIME_INTERVAL = 30.0
    MAX_RETRIES = 3
    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            auth: GRVTPerpetualAuth,
            connector: 'GRVTPerpetualDerivative',
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__()
        self._domain = domain
        self._api_factory = api_factory
        self._auth = auth
        self._connector = connector
        self._ws_assistant: Optional[WSAssistant] = None
        self._manage_ws_task = None

    async def _get_ws_assistant(self) -> WSAssistant:
        """
        Creates a new WSAssistant instance.
        """
        return await self._api_factory.get_ws_assistant()

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange.
        """
        ws = await self._get_ws_assistant()
        
        # GRVT uses authenticated WebSocket connection
        url = web_utils.wss_url(CONSTANTS.PRIVATE_WS_ENDPOINT, self._domain)
        
        # Add auth parameters to URL if needed
        # For GRVT, authentication might be done through the connection params
        auth_params = self._auth.get_auth_headers()
        
        self.logger().info(f"Connecting to GRVT user stream at {url}")
        await ws.connect(ws_url=url, ping_timeout=self.HEARTBEAT_TIME_INTERVAL)
        self.logger().info("Successfully connected to user stream")

        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to the user event channels through the provided websocket connection.

        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """
        # GRVT typically uses specific channel subscriptions for user data
        try:
            # Subscribe to private channels
            payload = {
                "method": "SUBSCRIBE",
                "params": ["order", "position", "balance"],
                "id": 1,
            }
            
            from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
            subscribe_request = WSJSONRequest(payload)
            await websocket_assistant.send(subscribe_request)
            
            self.logger().info("Subscribed to user order, position, and balance channels")
        except Exception as e:
            self.logger().error(f"Error subscribing to user channels: {e}")
            raise

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        """
        Handles websocket disconnection by cleaning up resources.

        :param websocket_assistant: The websocket assistant that was disconnected
        """
        self.logger().info("User stream interrupted. Cleaning up...")

        # Disconnect the websocket if it exists
        if websocket_assistant:
            await websocket_assistant.disconnect()
        self._ws_assistant = None
