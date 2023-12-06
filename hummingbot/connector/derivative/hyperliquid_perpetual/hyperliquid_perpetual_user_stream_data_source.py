import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_web_utils as web_utils
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_derivative import (
        HyperliquidPerpetualDerivative,
    )


class HyperliquidPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800  # Recommended to Ping/Update listen key to keep connection alive
    HEARTBEAT_TIME_INTERVAL = 30.0
    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            auth: AuthBase,
            trading_pairs: List[str],
            connector: 'HyperliquidPerpetualDerivative',
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

        self.token = None

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
        Creates an instance of WSAssistant connected to the exchange
        """
        ws: WSAssistant = await self._get_ws_assistant()
        url = f"{web_utils.wss_url(self._domain)}"
        await ws.connect(ws_url=url, ping_timeout=self.HEARTBEAT_TIME_INTERVAL)
        safe_ensure_future(self._ping_thread(ws))
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to order events.

        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """
        try:
            orders_change_payload = {
                "method": "subscribe",
                "subscription": {
                    "type": "orderUpdates",
                    "user": self._connector.hyperliquid_perpetual_api_key,
                }
            }
            subscribe_order_change_request: WSJSONRequest = WSJSONRequest(
                payload=orders_change_payload,
                is_auth_required=True)

            positions_payload = {
                "method": "subscribe",
                "subscription": {
                    "type": "user",
                    "user": self._connector.hyperliquid_perpetual_api_key,
                }
            }
            subscribe_positions_request: WSJSONRequest = WSJSONRequest(
                payload=positions_payload,
                is_auth_required=True)
            await websocket_assistant.send(subscribe_order_change_request)
            await websocket_assistant.send(subscribe_positions_request)

            self.logger().info("Subscribed to private order and trades changes channels...")
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
                "message": f"Error received via websocket - {err_msg}."
            })
        elif event_message.get("channel") in [
            CONSTANTS.USER_ORDERS_ENDPOINT_NAME,
            CONSTANTS.USEREVENT_ENDPOINT_NAME,
        ]:
            queue.put_nowait(event_message)

    async def _ping_thread(self, websocket_assistant: WSAssistant,):
        try:
            while True:
                ping_request = WSJSONRequest(payload={"method": "ping"})
                await asyncio.sleep(CONSTANTS.HEARTBEAT_TIME_INTERVAL)
                await websocket_assistant.send(ping_request)
        except Exception as e:
            self.logger().debug(f'ping error {e}')

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        while True:
            try:
                await super()._process_websocket_messages(
                    websocket_assistant=websocket_assistant,
                    queue=queue)
            except asyncio.TimeoutError:
                ping_request = WSJSONRequest(payload={"method": "ping"})
                await websocket_assistant.send(ping_request)
