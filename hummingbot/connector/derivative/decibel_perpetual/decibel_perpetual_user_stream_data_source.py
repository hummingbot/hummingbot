import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_web_utils as web_utils
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
        DecibelPerpetualDerivative,
    )


class DecibelPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800
    HEARTBEAT_TIME_INTERVAL = 30.0
    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            auth: AuthBase,
            trading_pairs: List[str],
            connector: 'DecibelPerpetualDerivative',
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__()
        self._domain = domain
        self._api_factory = api_factory
        self._auth = auth
        self._connector = connector
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
        url = web_utils.wss_url(self._domain)
        # Decibel uses Sec-Websocket-Protocol for auth
        protocols = []
        if hasattr(self._auth, "get_ws_protocols"):
            protocols = self._auth.get_ws_protocols()
        await ws.connect(
            ws_url=url,
            ping_timeout=self.HEARTBEAT_TIME_INTERVAL,
            ws_headers={"Sec-Websocket-Protocol": ", ".join(protocols)} if protocols else {},
        )
        safe_ensure_future(self._ping_thread(ws))
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        try:
            account_address = self._connector.decibel_account_address

            # Subscribe to order updates
            order_update_payload = {
                "method": "subscribe",
                "topic": f"{CONSTANTS.WS_ORDER_UPDATE_TOPIC}:{account_address}",
            }
            await websocket_assistant.send(
                WSJSONRequest(payload=order_update_payload, is_auth_required=True)
            )

            # Subscribe to account positions
            positions_payload = {
                "method": "subscribe",
                "topic": f"{CONSTANTS.WS_ACCOUNT_POSITIONS_TOPIC}:{account_address}",
            }
            await websocket_assistant.send(
                WSJSONRequest(payload=positions_payload, is_auth_required=True)
            )

            # Subscribe to account open orders
            open_orders_payload = {
                "method": "subscribe",
                "topic": f"{CONSTANTS.WS_ACCOUNT_OPEN_ORDERS_TOPIC}:{account_address}",
            }
            await websocket_assistant.send(
                WSJSONRequest(payload=open_orders_payload, is_auth_required=True)
            )

            # Subscribe to account overview (balance updates)
            overview_payload = {
                "method": "subscribe",
                "topic": f"{CONSTANTS.WS_ACCOUNT_OVERVIEW_TOPIC}:{account_address}",
            }
            await websocket_assistant.send(
                WSJSONRequest(payload=overview_payload, is_auth_required=True)
            )

            self.logger().info("Subscribed to private order, position, and balance channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to user streams...")
            raise

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if event_message.get("error") is not None:
            err_msg = event_message.get("error", {}).get("message", event_message.get("error"))
            raise IOError({
                "label": "WSS_ERROR",
                "message": f"Error received via websocket - {err_msg}.",
            })
        topic = event_message.get("topic", "")
        if any(
            topic.startswith(prefix)
            for prefix in [
                CONSTANTS.WS_ORDER_UPDATE_TOPIC,
                CONSTANTS.WS_ACCOUNT_POSITIONS_TOPIC,
                CONSTANTS.WS_ACCOUNT_OPEN_ORDERS_TOPIC,
                CONSTANTS.WS_ACCOUNT_OVERVIEW_TOPIC,
            ]
        ):
            queue.put_nowait(event_message)

    async def _ping_thread(self, websocket_assistant: WSAssistant):
        try:
            while True:
                ping_request = WSJSONRequest(payload={"method": "ping"})
                await asyncio.sleep(CONSTANTS.HEARTBEAT_TIME_INTERVAL)
                await websocket_assistant.send(ping_request)
        except Exception as e:
            self.logger().debug(f"Ping error: {e}")

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        while True:
            try:
                await super()._process_websocket_messages(
                    websocket_assistant=websocket_assistant,
                    queue=queue,
                )
            except asyncio.TimeoutError:
                ping_request = WSJSONRequest(payload={"method": "ping"})
                await websocket_assistant.send(ping_request)
