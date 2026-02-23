import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_web_utils as web_utils
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_auth import GrvtPerpetualAuth
    from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_derivative import (
        GrvtPerpetualDerivative,
    )


class GrvtPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    """
    User stream data source for GRVT Perpetual.

    Connects to the authenticated trade WebSocket endpoint and subscribes
    to order, fill, and position channels.
    """

    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800
    HEARTBEAT_TIME_INTERVAL = 30.0

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: "GrvtPerpetualAuth",
        trading_pairs: List[str],
        connector: "GrvtPerpetualDerivative",
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
        """
        Creates an instance of WSAssistant connected to the GRVT authenticated
        trade WebSocket endpoint with session cookie auth.
        """
        # Ensure we have a valid session before connecting
        await self._auth.ensure_session()

        ws: WSAssistant = await self._get_ws_assistant()
        url = web_utils.trade_wss_url(self._domain)

        # Connect with authentication headers (session cookie)
        auth_headers = self._auth.get_ws_auth_headers()
        await ws.connect(
            ws_url=url,
            ping_timeout=self.HEARTBEAT_TIME_INTERVAL,
            ws_headers=auth_headers,
        )
        safe_ensure_future(self._ping_thread(ws))
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to order, fill, and position events on the authenticated
        trade WebSocket.

        GRVT WS subscription format for trade streams:
        {"method": "subscribe", "params": {"channel": "order"}}
        """
        try:
            # Subscribe to order updates
            orders_payload = {
                "method": "subscribe",
                "params": {
                    "channel": CONSTANTS.WS_ORDER_CHANNEL,
                },
            }
            subscribe_orders_request = WSJSONRequest(
                payload=orders_payload,
                is_auth_required=True,
            )

            # Subscribe to fill updates
            fills_payload = {
                "method": "subscribe",
                "params": {
                    "channel": CONSTANTS.WS_FILL_CHANNEL,
                },
            }
            subscribe_fills_request = WSJSONRequest(
                payload=fills_payload,
                is_auth_required=True,
            )

            # Subscribe to position updates
            positions_payload = {
                "method": "subscribe",
                "params": {
                    "channel": CONSTANTS.WS_POSITION_CHANNEL,
                },
            }
            subscribe_positions_request = WSJSONRequest(
                payload=positions_payload,
                is_auth_required=True,
            )

            await websocket_assistant.send(subscribe_orders_request)
            await websocket_assistant.send(subscribe_fills_request)
            await websocket_assistant.send(subscribe_positions_request)

            self.logger().info("Subscribed to private order, fill, and position channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to user streams...")
            raise

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if event_message.get("error") is not None:
            err_msg = event_message.get("error", {})
            if isinstance(err_msg, dict):
                err_msg = err_msg.get("message", str(err_msg))
            raise IOError(
                {
                    "label": "WSS_ERROR",
                    "message": f"Error received via websocket - {err_msg}.",
                }
            )
        channel = event_message.get("channel", "")
        if channel in [
            CONSTANTS.WS_ORDER_CHANNEL,
            CONSTANTS.WS_ORDER_STATE_CHANNEL,
            CONSTANTS.WS_FILL_CHANNEL,
            CONSTANTS.WS_POSITION_CHANNEL,
        ]:
            queue.put_nowait(event_message)

    async def _ping_thread(self, websocket_assistant: WSAssistant):
        try:
            while True:
                ping_request = WSJSONRequest(payload={"method": "ping"})
                await asyncio.sleep(CONSTANTS.HEARTBEAT_TIME_INTERVAL)
                await websocket_assistant.send(ping_request)
        except Exception as e:
            self.logger().debug(f"Ping error: {e}")

    async def _process_websocket_messages(
        self,
        websocket_assistant: WSAssistant,
        queue: asyncio.Queue,
    ):
        while True:
            try:
                await super()._process_websocket_messages(
                    websocket_assistant=websocket_assistant,
                    queue=queue,
                )
            except asyncio.TimeoutError:
                ping_request = WSJSONRequest(payload={"method": "ping"})
                await websocket_assistant.send(ping_request)
