import asyncio
import logging
from typing import TYPE_CHECKING, Any, Dict, Optional

from hummingbot.connector.exchange.coinmate import coinmate_constants as CONSTANTS
from hummingbot.connector.exchange.coinmate.coinmate_auth import CoinmateAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import (
    UserStreamTrackerDataSource,
)
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.coinmate.coinmate_exchange import (
        CoinmateExchange,
    )


class CoinmateAPIUserStreamDataSource(UserStreamTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None
    HEARTBEAT_TIME_INTERVAL = 30.0
    MAX_RETRIES = 3

    def __init__(
        self,
        auth: CoinmateAuth,
        connector: "CoinmateExchange",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._auth = auth
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain

    async def _get_ws_assistant(self) -> WSAssistant:
        return await self._api_factory.get_ws_assistant()

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws = await self._get_ws_assistant()
        await ws.connect(
            ws_url=CONSTANTS.WSS_URL, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL
        )
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        try:
            client_id = self._auth.client_id

            # Subscribe to user data channels
            channels = [
                "private-open_orders",
                "private-user_balances",
                "private-user-trades",
            ]

            for channel in channels:
                auth_data = self._auth.get_ws_auth_data()
                payload = {
                    "event": "subscribe",
                    "data": {"channel": f"{channel}-{client_id}", **auth_data},
                }
                subscribe_request = WSJSONRequest(payload=payload)
                await asyncio.sleep(0.1)
                await websocket_assistant.send(subscribe_request)

            self.logger().info(
                "Subscribed to private user channels (orders, balances, trades)"
            )

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to user streams", exc_info=True
            )
            raise

    async def _process_websocket_messages(
        self, websocket_assistant: WSAssistant, queue: asyncio.Queue
    ):
        async for ws_response in websocket_assistant.iter_messages():
            try:
                message = ws_response.data
                if isinstance(message, dict):
                    await self._process_event_message(
                        message, queue
                    )
                else:
                    self.logger().debug(
                        f"Received non-dict message: {type(message)}"
                    )
            except Exception as e:
                self.logger().error(
                    f"Error processing WebSocket message: {e}", exc_info=True
                )

    async def _process_event_message(
        self,
        event_message: Dict[str, Any],
        queue: asyncio.Queue,
    ):
        """Process incoming websocket messages and handle different event types."""
        try:
            event_type = event_message.get("event")
            
            if event_type == "data":
                # Pass the raw message to the exchange for processing
                channel = event_message.get("channel", "")
                private_channels = [
                    "private-open_orders",
                    "private-user_balances",
                    "private-user-trades"
                ]
                if any(ch in channel for ch in private_channels):
                    queue.put_nowait(event_message)
                else:
                    self.logger().debug(f"Unknown channel type: {channel}")
                    
            elif event_type == "subscribe_success":
                channel = event_message.get("data", {}).get("channel", "unknown")
                self.logger().info(f"Successfully subscribed to: {channel}")
                
            elif event_type == "unsubscribe_success":
                channel = event_message.get("data", {}).get("channel", "unknown")
                self.logger().info(f"Successfully unsubscribed from: {channel}")

            elif event_type == "error":
                error_msg = event_message.get("message", "Unknown error")
                self.logger().error(f"WebSocket error: {error_msg}")
                
            else:
                self.logger().debug(f"Unhandled event type: {event_type}")

        except Exception as e:
            self.logger().error(f"Error processing event message: {e}", exc_info=True)

    async def _on_user_stream_interruption(
        self, websocket_assistant: Optional[WSAssistant]
    ):
        self.logger().info("User stream interrupted. Cleaning up...")
        if websocket_assistant:
            await websocket_assistant.disconnect()
        await super()._on_user_stream_interruption(websocket_assistant)

    async def _send_ping(self, websocket_assistant: WSAssistant):
        pass
