import asyncio
from typing import TYPE_CHECKING, Any, Dict, Optional

import hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_auth import EvedexPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_derivative import EvedexPerpetualDerivative


class EvedexPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    """
    User stream data source for Evedex Perpetual.

    Uses Centrifuge protocol with channel naming patterns:
    - Orders: order-{userExchangeId}
    - Positions: position-{userExchangeId}
    - Account: user-{userExchangeId}
    - Order Fills: orderFills-{userExchangeId}
    - Funding: funding-{userExchangeId}
    """
    HEARTBEAT_TIME_INTERVAL = 25.0  # Centrifugo ping interval (send before server timeout)
    PING_TIMEOUT = 10.0  # How long to wait for pong response

    _logger: Optional[HummingbotLogger] = None

    _message_id: int = 0

    def __init__(
            self,
            auth: EvedexPerpetualAuth,
            connector: 'EvedexPerpetualDerivative',
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._domain = domain
        self._api_factory = api_factory
        self._auth = auth
        self._connector = connector
        self._user_exchange_id: Optional[str] = None
        self._ping_task: Optional[asyncio.Task] = None
        self._ws_assistant: Optional[WSAssistant] = None

    def _next_message_id(self) -> int:
        """Generate the next message ID for Centrifugo protocol."""
        self._message_id += 1
        return self._message_id

    async def _ping_loop(self, websocket_assistant: WSAssistant):
        """
        Sends Centrifugo protocol ping messages to keep the connection alive.
        Centrifugo uses application-level pings, not just WebSocket pings.
        """
        try:
            while True:
                await asyncio.sleep(self.HEARTBEAT_TIME_INTERVAL)
                # Centrifugo protocol ping - empty object indicates ping
                ping_payload = {"ping": {}}
                ping_request: WSJSONRequest = WSJSONRequest(payload=ping_payload)
                await websocket_assistant.send(ping_request)
                self.logger().debug("Sent Centrifugo ping")
        except asyncio.CancelledError:
            self.logger().debug("Ping loop cancelled")
            raise
        except Exception as e:
            self.logger().warning(f"Ping loop error: {e}")

    async def _get_access_token(self) -> str:
        """
        Get or refresh the access token for WebSocket authentication.
        Always delegates to auth class which handles token refresh/expiry.
        """
        # Always get from auth class - it handles caching and refresh internally
        return await self._auth.get_access_token()

    async def _get_user_exchange_id(self) -> str:
        """
        Get the userExchangeId required for Centrifuge channel subscriptions.
        """
        if self._user_exchange_id is None:
            user_info = await self._connector._api_get(
                path_url=CONSTANTS.USER_ME_PATH_URL,
                is_auth_required=True,
                limit_id=CONSTANTS.USER_ME_PATH_URL
            )
            self._user_exchange_id = str(user_info.get("exchangeId", ""))
        return self._user_exchange_id

    async def _get_ws_assistant(self) -> WSAssistant:
        """
        Creates a new WSAssistant instance.
        """
        return await self._api_factory.get_ws_assistant()

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange.
        """
        # Cancel any existing ping task
        if self._ping_task is not None and not self._ping_task.done():
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
            self._ping_task = None

        ws = await self._get_ws_assistant()
        url = web_utils.wss_url(self._domain)

        self.logger().info(f"Connecting to user stream at {url}")
        await ws.connect(ws_url=url, ping_timeout=self.HEARTBEAT_TIME_INTERVAL + self.PING_TIMEOUT)

        # Send Centrifugo connect message (no token - auth is per-subscription)
        connect_payload = {
            "connect": {"name": "js"},
            "id": self._next_message_id()
        }
        connect_request: WSJSONRequest = WSJSONRequest(payload=connect_payload)
        await ws.send(connect_request)

        # Centrifugo server sends pings; respond with pong in message handler.
        self._ws_assistant = ws

        self.logger().info("Successfully connected to user stream")

        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to the user stream channels through the provided websocket connection.
        Uses Centrifugo protocol with accessToken in each subscription.

        Channel patterns (using dash separator):
        - futures-perp:heartbeat: Heartbeat channel (public)
        - futures-perp:order-{userExchangeId}: User orders
        - futures-perp:position-{userExchangeId}: User positions
        - futures-perp:user-{userExchangeId}: User account updates
        - futures-perp:orderFilled-{userExchangeId}: Order fills

        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """
        try:
            # Get userExchangeId and access token for channel subscriptions
            user_exchange_id = await self._get_user_exchange_id()
            access_token = await self._get_access_token()

            # Subscribe to heartbeat channel (public, no auth required)
            heartbeat_payload = {
                "subscribe": {
                    "channel": "futures-perp:heartbeat",
                    "flag": 1,
                    "recover": True
                },
                "id": self._next_message_id()
            }
            subscribe_heartbeat_request: WSJSONRequest = WSJSONRequest(payload=heartbeat_payload)
            await websocket_assistant.send(subscribe_heartbeat_request)

            # Subscribe to user orders channel: futures-perp:order-{userExchangeId}
            orders_payload = {
                "subscribe": {
                    "channel": f"futures-perp:order-{user_exchange_id}",
                    "data": {"accessToken": access_token},
                    "recoverable": True,
                    "flag": 1,
                    "recover": True
                },
                "id": self._next_message_id()
            }
            subscribe_orders_request: WSJSONRequest = WSJSONRequest(payload=orders_payload)
            await websocket_assistant.send(subscribe_orders_request)

            # Subscribe to user positions channel: futures-perp:position-{userExchangeId}
            positions_payload = {
                "subscribe": {
                    "channel": f"futures-perp:position-{user_exchange_id}",
                    "data": {"accessToken": access_token},
                    "recoverable": True,
                    "flag": 1,
                    "recover": True
                },
                "id": self._next_message_id()
            }
            subscribe_positions_request: WSJSONRequest = WSJSONRequest(payload=positions_payload)
            await websocket_assistant.send(subscribe_positions_request)

            # Subscribe to user account channel: futures-perp:user-{userExchangeId}
            account_payload = {
                "subscribe": {
                    "channel": f"futures-perp:user-{user_exchange_id}",
                    "data": {"accessToken": access_token},
                    "recoverable": True,
                    "flag": 1,
                    "recover": True
                },
                "id": self._next_message_id()
            }
            subscribe_account_request: WSJSONRequest = WSJSONRequest(payload=account_payload)
            await websocket_assistant.send(subscribe_account_request)

            # Subscribe to order fills channel: futures-perp:orderFilled-{userExchangeId}
            order_fills_payload = {
                "subscribe": {
                    "channel": f"futures-perp:orderFilled-{user_exchange_id}",
                    "data": {"accessToken": access_token},
                    "recoverable": True,
                    "flag": 1,
                    "recover": True
                },
                "id": self._next_message_id()
            }
            subscribe_order_fills_request: WSJSONRequest = WSJSONRequest(payload=order_fills_payload)
            await websocket_assistant.send(subscribe_order_fills_request)

            self.logger().info(f"Subscribed to private user stream channels for user {user_exchange_id}...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to user stream channels...")
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data
            # Centrifugo sends ping commands and expects pong replies.
            if data == {}:
                await websocket_assistant.send(WSJSONRequest(payload={}))
                continue
            if isinstance(data, dict) and "ping" in data:
                self.logger().debug("Received Centrifugo ping on perpetual user stream; sending pong.")
                await websocket_assistant.send(WSJSONRequest(payload={"pong": {}}))
                continue
            await self._process_event_message(event_message=data, queue=queue)

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        """
        Called when the user stream gets interrupted.
        Cleans up the ping task and connection state.
        """
        # Cancel the ping task
        if self._ping_task is not None and not self._ping_task.done():
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
            self._ping_task = None

        self._ws_assistant = None
        await super()._on_user_stream_interruption(websocket_assistant=websocket_assistant)

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        # Handle empty pong responses from Centrifugo ping (ignore them)
        if not event_message or event_message == {}:
            self.logger().debug("Received Centrifugo pong")
            return

        # Handle top-level errors (connection errors, etc.)
        if "error" in event_message:
            error_data = event_message.get("error", {})
            # Handle both string and dict error formats
            if isinstance(error_data, dict):
                err_msg = error_data.get("message", str(error_data))
                err_code = error_data.get("code", 0)
            else:
                err_msg = str(error_data)
                err_code = 0
            # Only disconnect for critical errors (code 100+ typically are client errors)
            if err_code >= 100 or "permission" in err_msg.lower():
                self.logger().warning(f"WebSocket error (code {err_code}): {err_msg}")
                # Don't raise - just log the warning and continue
                return
            raise IOError({
                "label": "WSS_ERROR",
                "message": f"Error received via websocket - {err_msg}."
            })

        if "push" in event_message:
            await queue.put(event_message)
