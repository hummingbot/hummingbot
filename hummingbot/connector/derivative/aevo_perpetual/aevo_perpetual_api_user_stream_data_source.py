import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.aevo_perpetual import (
    aevo_perpetual_constants as CONSTANTS,
    aevo_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_auth import AevoPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSResponse
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_derivative import AevoPerpetualDerivative


class AevoPerpetualAPIUserStreamDataSource(UserStreamTrackerDataSource):
    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800
    WS_HEARTBEAT_TIME_INTERVAL = 30.0
    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            auth: AevoPerpetualAuth,
            trading_pairs: List[str],
            connector: 'AevoPerpetualDerivative',
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._domain = domain
        self._api_factory = api_factory
        self._auth = auth
        self._ws_assistants: List[WSAssistant] = []
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

    async def _authenticate(self, ws: WSAssistant):
        auth_payload = self._auth.get_ws_auth_payload()
        auth_request: WSJSONRequest = WSJSONRequest(payload=auth_payload)
        await ws.send(auth_request)
        response: WSResponse = await ws.receive()
        message = response.data
        if isinstance(message, dict) and message.get("error") is not None:
            raise IOError(f"Websocket authentication failed: {message['error']}")

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._get_ws_assistant()
        url = f"{web_utils.wss_url(self._domain)}"
        await ws.connect(ws_url=url, ping_timeout=self.WS_HEARTBEAT_TIME_INTERVAL)
        safe_ensure_future(self._ping_thread(ws))
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        try:
            await self._authenticate(websocket_assistant)

            subscribe_payload = {
                "op": "subscribe",
                "data": [
                    CONSTANTS.WS_ORDERS_CHANNEL,
                    CONSTANTS.WS_FILLS_CHANNEL,
                    CONSTANTS.WS_POSITIONS_CHANNEL,
                ],
            }
            subscribe_request: WSJSONRequest = WSJSONRequest(payload=subscribe_payload)
            await websocket_assistant.send(subscribe_request)

            self.logger().info("Subscribed to private orders, fills and positions channels...")
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
        if event_message.get("channel") in [
            CONSTANTS.WS_ORDERS_CHANNEL,
            CONSTANTS.WS_FILLS_CHANNEL,
            CONSTANTS.WS_POSITIONS_CHANNEL,
        ]:
            queue.put_nowait(event_message)

    async def _ping_thread(self, websocket_assistant: WSAssistant):
        try:
            ping_id = 1
            while True:
                ping_request = WSJSONRequest(payload={"op": "ping", "id": ping_id})
                await asyncio.sleep(self.WS_HEARTBEAT_TIME_INTERVAL)
                await websocket_assistant.send(ping_request)
                ping_id += 1
        except Exception as exc:
            self.logger().debug(f"Ping error {exc}")

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        while True:
            try:
                await super()._process_websocket_messages(
                    websocket_assistant=websocket_assistant,
                    queue=queue)
            except asyncio.TimeoutError:
                ping_request = WSJSONRequest(payload={"op": "ping", "id": 1})
                await websocket_assistant.send(ping_request)
