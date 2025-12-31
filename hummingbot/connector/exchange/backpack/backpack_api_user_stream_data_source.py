import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.backpack import (
    backpack_constants as CONSTANTS,
    backpack_web_utils as web_utils,
)
from hummingbot.connector.exchange.backpack.backpack_auth import BackpackAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.backpack.backpack_exchange import BackpackExchange


class BackpackAPIUserStreamDataSource(UserStreamTrackerDataSource):
    """
    User stream data source for Backpack Exchange.

    Handles private WebSocket streams for:
    - Order updates
    - Balance updates
    - Fill/trade events
    """

    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800  # 30 minutes
    HEARTBEAT_TIME_INTERVAL = 30.0
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: BackpackAuth,
        trading_pairs: List[str],
        connector: "BackpackExchange",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        """
        Initialize the user stream data source.

        Args:
            auth: Authentication handler for signing
            trading_pairs: List of trading pairs to track
            connector: The exchange connector instance
            api_factory: Factory for creating API assistants
            domain: Exchange domain (mainnet or testnet)
        """
        super().__init__()
        self._domain = domain
        self._api_factory = api_factory
        self._auth = auth
        self._ws_assistants: List[WSAssistant] = []
        self._connector = connector
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._last_listen_key_ping_ts = None
        self._trading_pairs: List[str] = trading_pairs

    @property
    def last_recv_time(self) -> float:
        """Get the timestamp of the last received message."""
        if self._ws_assistant:
            return self._ws_assistant.last_recv_time
        return 0

    async def _get_ws_assistant(self) -> WSAssistant:
        """Get or create the WebSocket assistant."""
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Create and connect a WebSocket assistant.

        Returns:
            Connected WSAssistant
        """
        ws: WSAssistant = await self._get_ws_assistant()
        url = web_utils.wss_url(self._domain)
        await ws.connect(ws_url=url, ping_timeout=self.HEARTBEAT_TIME_INTERVAL)
        safe_ensure_future(self._ping_thread(ws))
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribe to private user channels with signed authentication.

        Args:
            websocket_assistant: The WebSocket assistant to use
        """
        try:
            # Build list of private streams to subscribe to
            streams = [CONSTANTS.WS_ORDER_UPDATE_CHANNEL]

            # Generate signed subscription payload
            subscribe_payload = self._auth.generate_ws_auth_payload(streams)

            subscribe_request: WSJSONRequest = WSJSONRequest(
                payload=subscribe_payload,
                is_auth_required=True,
            )

            await websocket_assistant.send(subscribe_request)

            self.logger().info("Subscribed to private order update channel...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to user streams...")
            raise

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        """
        Process incoming WebSocket event messages.

        Args:
            event_message: The parsed WebSocket message
            queue: Queue to put processed messages
        """
        # Check for errors
        if event_message.get("error") is not None:
            err_msg = event_message.get("error", {})
            if isinstance(err_msg, dict):
                err_msg = err_msg.get("message", str(err_msg))
            raise IOError({
                "label": "WSS_ERROR",
                "message": f"Error received via websocket - {err_msg}.",
            })

        # Check for subscription confirmation
        if event_message.get("result") is not None:
            self.logger().debug(f"Subscription confirmed: {event_message}")
            return

        # Process stream messages
        stream = event_message.get("stream", "")
        data = event_message.get("data", event_message)
        event_type = data.get("e") if isinstance(data, dict) else None
        if stream.startswith("account."):
            # Order updates, position updates, etc.
            queue.put_nowait(event_message)
        elif event_type and event_type.startswith("order"):
            queue.put_nowait(event_message)

    async def _ping_thread(self, websocket_assistant: WSAssistant):
        """
        Background task to send periodic ping messages.

        Args:
            websocket_assistant: The WebSocket assistant
        """
        try:
            while True:
                await asyncio.sleep(CONSTANTS.HEARTBEAT_TIME_INTERVAL)
                # Use websocket ping frames (Backpack WS does not accept JSON PING messages)
                await websocket_assistant.ping()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger().debug(f"Ping error: {e}")

    async def _process_websocket_messages(
        self,
        websocket_assistant: WSAssistant,
        queue: asyncio.Queue,
    ):
        """
        Process incoming WebSocket messages continuously.

        Args:
            websocket_assistant: The WebSocket assistant
            queue: Queue to put processed messages
        """
        while True:
            try:
                await super()._process_websocket_messages(
                    websocket_assistant=websocket_assistant,
                    queue=queue,
                )
            except asyncio.TimeoutError:
                # Send ping frame on timeout to keep connection alive
                await websocket_assistant.ping()

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        Main method to listen for user stream events.

        This connects to the WebSocket, subscribes to channels,
        and continuously processes messages.

        Args:
            output: Queue to put received messages
        """
        while True:
            try:
                ws_assistant = await self._connected_websocket_assistant()
                await self._subscribe_channels(ws_assistant)
                await self._process_websocket_messages(ws_assistant, output)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception(
                    "Unexpected error while listening to user stream. Retrying after 5 seconds..."
                )
                await self._sleep(5.0)
            finally:
                if self._ws_assistant is not None:
                    await self._ws_assistant.disconnect()
                    self._ws_assistant = None
