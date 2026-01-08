import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_web_utils as web_utils
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_derivative import (
        EvedexPerpetualDerivative,
    )


class EvedexPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800
    HEARTBEAT_TIME_INTERVAL = 30.0
    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            auth: AuthBase,
            trading_pairs: List[str],
            connector: "EvedexPerpetualDerivative",
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DOMAIN,
    ):
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
        if self._ws_assistant:
            return self._ws_assistant.last_recv_time
        return 0

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._get_ws_assistant()
        url = f"{web_utils.wss_url(self._domain)}"
        await ws.connect(ws_url=url, ping_timeout=self.HEARTBEAT_TIME_INTERVAL)
        
        # Authenticate the WebSocket connection
        await self._authenticate_ws(ws)
        
        safe_ensure_future(self._ping_thread(ws))
        return ws

    async def _authenticate_ws(self, ws: WSAssistant):
        """Authenticate the WebSocket connection using Centrifuge protocol."""
        auth_payload = self._auth.get_ws_auth_payload()
        
        # Centrifuge connect message with authentication
        connect_payload = {
            "id": 0,
            "method": 0,  # Connect method
            "params": {
                "token": "",  # JWT token if available
                "data": auth_payload
            }
        }
        
        connect_request = WSJSONRequest(payload=connect_payload)
        await ws.send(connect_request)
        
        # Wait for connection acknowledgment
        response = await ws.receive()
        if response.data.get("error"):
            raise Exception(f"WebSocket authentication failed: {response.data.get(error)}")

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        try:
            wallet_address = self._auth.wallet_address
            
            # Subscribe to order updates channel
            orders_payload = {
                "id": 1,
                "method": 1,  # Subscribe method
                "params": {
                    "channel": f"{CONSTANTS.WS_USER_ORDERS_CHANNEL}:{wallet_address}"
                }
            }
            subscribe_orders_request = WSJSONRequest(
                payload=orders_payload,
                is_auth_required=True)

            # Subscribe to user trades channel
            trades_payload = {
                "id": 2,
                "method": 1,
                "params": {
                    "channel": f"{CONSTANTS.WS_USER_TRADES_CHANNEL}:{wallet_address}"
                }
            }
            subscribe_trades_request = WSJSONRequest(
                payload=trades_payload,
                is_auth_required=True)

            # Subscribe to positions channel
            positions_payload = {
                "id": 3,
                "method": 1,
                "params": {
                    "channel": f"{CONSTANTS.WS_USER_POSITIONS_CHANNEL}:{wallet_address}"
                }
            }
            subscribe_positions_request = WSJSONRequest(
                payload=positions_payload,
                is_auth_required=True)

            # Subscribe to balance channel
            balance_payload = {
                "id": 4,
                "method": 1,
                "params": {
                    "channel": f"{CONSTANTS.WS_USER_BALANCE_CHANNEL}:{wallet_address}"
                }
            }
            subscribe_balance_request = WSJSONRequest(
                payload=balance_payload,
                is_auth_required=True)

            await websocket_assistant.send(subscribe_orders_request)
            await websocket_assistant.send(subscribe_trades_request)
            await websocket_assistant.send(subscribe_positions_request)
            await websocket_assistant.send(subscribe_balance_request)

            self.logger().info("Subscribed to private order, trades, positions, and balance channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to user streams...")
            raise

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if event_message.get("error") is not None:
            err_msg = event_message.get("error", {}).get("message", str(event_message.get("error")))
            raise IOError({
                "label": "WSS_ERROR",
                "message": f"Error received via websocket - {err_msg}."
            })
        
        # Handle Centrifuge push messages
        push_data = event_message.get("push", {})
        channel = push_data.get("channel", "")
        
        if any(ch in channel for ch in [
            CONSTANTS.WS_USER_ORDERS_CHANNEL,
            CONSTANTS.WS_USER_TRADES_CHANNEL,
            CONSTANTS.WS_USER_POSITIONS_CHANNEL,
            CONSTANTS.WS_USER_BALANCE_CHANNEL
        ]):
            queue.put_nowait(event_message)

    async def _ping_thread(self, websocket_assistant: WSAssistant):
        try:
            while True:
                # Centrifuge ping message
                ping_request = WSJSONRequest(payload={"method": 7})  # Ping method
                await asyncio.sleep(CONSTANTS.HEARTBEAT_TIME_INTERVAL)
                await websocket_assistant.send(ping_request)
        except Exception as e:
            self.logger().debug(f"Ping error: {e}")

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        while True:
            try:
                await super()._process_websocket_messages(
                    websocket_assistant=websocket_assistant,
                    queue=queue)
            except asyncio.TimeoutError:
                ping_request = WSJSONRequest(payload={"method": 7})
                await websocket_assistant.send(ping_request)
