import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.backpack_perpetual import (
    backpack_perpetual_constants as CONSTANTS,
    backpack_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_auth import BackpackPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_derivative import (
        BackpackPerpetualDerivative,
    )


class BackpackPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    """
    User stream data source for Backpack Perpetual.

    Handles private WebSocket streams for:
    - Order updates
    - Position updates
    - Fill/trade events
    """

    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800  # 30 minutes
    HEARTBEAT_TIME_INTERVAL = 30.0
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: BackpackPerpetualAuth,
        trading_pairs: List[str],
        connector: "BackpackPerpetualDerivative",
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
        url = web_utils.wss_url(self._domain)
        await ws.connect(ws_url=url, ping_timeout=self.HEARTBEAT_TIME_INTERVAL)
        safe_ensure_future(self._ping_thread(ws))
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        try:
            # Subscribe to order updates and position updates
            streams = [
                CONSTANTS.WS_ORDER_UPDATE_CHANNEL,
                CONSTANTS.WS_POSITION_UPDATE_CHANNEL,
            ]

            subscribe_payload = self._auth.generate_ws_auth_payload(streams)

            subscribe_request: WSJSONRequest = WSJSONRequest(
                payload=subscribe_payload,
                is_auth_required=True,
            )

            await websocket_assistant.send(subscribe_request)

            self.logger().info("Subscribed to private order and position update channels...")
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
            raise IOError({
                "label": "WSS_ERROR",
                "message": f"Error received via websocket - {err_msg}.",
            })

        if event_message.get("result") is not None:
            self.logger().debug(f"Subscription confirmed: {event_message}")
            return

        stream = event_message.get("stream", "")
        data = event_message.get("data", event_message)
        event_type = data.get("e") if isinstance(data, dict) else None
        if stream.startswith("account."):
            # Order updates, position updates, etc.
            queue.put_nowait(event_message)
        elif event_type and (event_type.startswith("order") or event_type.startswith("position")):
            queue.put_nowait(event_message)

    async def _ping_thread(self, websocket_assistant: WSAssistant):
        try:
            while True:
                await asyncio.sleep(CONSTANTS.HEARTBEAT_TIME_INTERVAL)
                ping_request = WSJSONRequest(payload={"method": "PING"})
                await websocket_assistant.send(ping_request)
        except asyncio.CancelledError:
            pass
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
                ping_request = WSJSONRequest(payload={"method": "PING"})
                await websocket_assistant.send(ping_request)

    async def listen_for_user_stream(self, output: asyncio.Queue):
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
