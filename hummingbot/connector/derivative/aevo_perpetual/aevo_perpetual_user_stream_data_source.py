import asyncio
import time
from typing import Any, Dict, List, Optional

from hummingbot.connector.derivative.aevo_perpetual import aevo_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.aevo_perpetual import aevo_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_auth import AevoPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class AevoPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: AevoPerpetualAuth,
        trading_pairs: List[str],
        connector: "AevoPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__()
        self._auth = auth
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._last_recv_time: float = 0

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Create and connect WebSocket assistant.
        """
        ws_url = web_utils.wss_url(domain=self._domain)
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=ws_url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _authenticate(self, ws: WSAssistant):
        """
        Send authentication message to WebSocket.
        """
        auth_payload = self._auth.get_ws_auth_payload()
        await ws.send(WSJSONRequest(payload=auth_payload))

        async for ws_response in ws.iter_messages():
            data = ws_response.data
            if data.get("op") == "auth" and data.get("success"):
                self.logger().info("WebSocket authentication successful")
                break
            elif data.get("error"):
                raise Exception(f"WebSocket authentication failed: {data.get('error')}")

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribe to private user channels.
        """
        subscribe_payload = {
            "op": "subscribe",
            "data": [
                CONSTANTS.WS_ORDERS_CHANNEL,
                CONSTANTS.WS_FILLS_CHANNEL,
                CONSTANTS.WS_POSITIONS_CHANNEL,
            ],
        }
        await ws.send(WSJSONRequest(payload=subscribe_payload))

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        """
        Process incoming user stream event message.
        """
        self._last_recv_time = time.time()
        channel = event_message.get("channel", "")

        if channel in [CONSTANTS.WS_ORDERS_CHANNEL, CONSTANTS.WS_FILLS_CHANNEL, CONSTANTS.WS_POSITIONS_CHANNEL]:
            queue.put_nowait(event_message)

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        """
        Process incoming WebSocket messages.
        """
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data
            self._last_recv_time = time.time()

            if data.get("channel"):
                await self._process_event_message(data, queue)

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        Main loop for user stream subscription handling.
        """
        ws: Optional[WSAssistant] = None
        while True:
            try:
                ws = await self._connected_websocket_assistant()
                await self._authenticate(ws)
                await self._subscribe_channels(ws)
                await self._process_websocket_messages(ws, output)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream WebSocket loop")
                await self._sleep(5.0)
            finally:
                ws and await ws.disconnect()
