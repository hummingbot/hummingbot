import asyncio
from typing import TYPE_CHECKING, List, Optional

from hummingbot.connector.derivative.backpack_perpetual import backpack_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_auth import BackpackPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_derivative import (
        BackpackPerpetualDerivative,
    )


class BackpackPerpetualAPIUserStreamDataSource(UserStreamTrackerDataSource):

    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 60  # Recommended to Ping/Update listen key to keep connection alive
    HEARTBEAT_TIME_INTERVAL = 30.0
    LISTEN_KEY_RETRY_INTERVAL = 5.0
    MAX_RETRIES = 3

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: AuthBase,
                 trading_pairs: List[str],
                 connector: 'BackpackPerpetualDerivative',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__()
        self._auth: BackpackPerpetualAuth = auth
        self._domain = domain
        self._api_factory = api_factory
        self._connector = connector

    async def _get_ws_assistant(self) -> WSAssistant:
        """
        Creates a new WSAssistant instance.
        """
        # Always create a new assistant to avoid connection issues
        return await self._api_factory.get_ws_assistant()

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange.

        This method ensures the listen key is ready before connecting.
        """
        # Get a websocket assistant and connect it
        ws = await self._get_ws_assistant()
        url = f"{CONSTANTS.WSS_URL.format(self._domain)}"

        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        self.logger().info("Successfully connected to user stream")

        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.

        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """
        try:
            timestamp_ms = int(self._auth.time_provider.time() * 1e3)
            signature = self._auth.generate_signature(params={},
                                                      timestamp_ms=timestamp_ms,
                                                      window_ms=self._auth.DEFAULT_WINDOW_MS,
                                                      instruction="subscribe")
            orders_change_payload = {
                "method": "SUBSCRIBE",
                "params": [CONSTANTS.ALL_ORDERS_CHANNEL],
                "signature": [
                    self._auth.api_key,
                    signature,
                    str(timestamp_ms),
                    str(self._auth.DEFAULT_WINDOW_MS)
                ]
            }

            suscribe_orders_change_payload: WSJSONRequest = WSJSONRequest(payload=orders_change_payload)

            positions_change_payload = {
                "method": "SUBSCRIBE",
                "params": [CONSTANTS.ALL_POSITIONS_CHANNEL],
                "signature": [
                    self._auth.api_key,
                    signature,
                    str(timestamp_ms),
                    str(self._auth.DEFAULT_WINDOW_MS)
                ]
            }

            suscribe_positions_change_payload: WSJSONRequest = WSJSONRequest(payload=positions_change_payload)

            await websocket_assistant.send(suscribe_orders_change_payload)
            await websocket_assistant.send(suscribe_positions_change_payload)

            self.logger().info("Subscribed to private order changes and position updates channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to user streams...")
            raise

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        """
        Handles websocket disconnection by cleaning up resources.

        :param websocket_assistant: The websocket assistant that was disconnected
        """
        # Disconnect the websocket if it exists
        websocket_assistant and await websocket_assistant.disconnect()
