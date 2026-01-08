import asyncio
import time
from typing import Any, Dict, List, Optional

from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_web_utils as web_utils
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class ArchitectPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth,
        trading_pairs: List[str],
        connector: "ArchitectPerpetualDerivative",
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
        Connect to the orders WebSocket.
        """
        ws = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=web_utils.orders_wss_url(self._domain))
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribe to user-specific channels (orders, positions, balances).
        """
        # Authenticate
        auth_request = WSJSONRequest(
            payload={
                "type": "auth",
                "api_key": self._auth.api_key,
            }
        )
        await websocket_assistant.send(auth_request)

        # Subscribe to order updates
        subscribe_orders = WSJSONRequest(
            payload={
                "type": "subscribe",
                "channel": "orders",
            }
        )
        await websocket_assistant.send(subscribe_orders)

        # Subscribe to position updates
        subscribe_positions = WSJSONRequest(
            payload={
                "type": "subscribe",
                "channel": "positions",
            }
        )
        await websocket_assistant.send(subscribe_positions)

        # Subscribe to balance updates
        subscribe_balances = WSJSONRequest(
            payload={
                "type": "subscribe",
                "channel": "balances",
            }
        )
        await websocket_assistant.send(subscribe_balances)

    async def _process_websocket_messages(
        self,
        websocket_assistant: WSAssistant,
        queue: asyncio.Queue,
    ):
        """
        Process incoming WebSocket messages and put them in the queue.
        """
        async for ws_response in websocket_assistant.iter_messages():
            self._last_recv_time = time.time()
            data = ws_response.data
            
            if data.get("type") in ["order_update", "position_update", "balance_update", "fill"]:
                queue.put_nowait(data)

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        """
        Handle WebSocket disconnection.
        """
        if websocket_assistant:
            await websocket_assistant.disconnect()

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        Main loop for listening to user stream.
        """
        ws = None
        while True:
            try:
                ws = await self._connected_websocket_assistant()
                await self._subscribe_channels(ws)
                await self._process_websocket_messages(ws, output)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"User stream error: {e}")
                await asyncio.sleep(5.0)
            finally:
                await self._on_user_stream_interruption(ws)
