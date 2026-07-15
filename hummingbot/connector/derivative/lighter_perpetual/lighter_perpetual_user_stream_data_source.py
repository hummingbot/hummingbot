import asyncio
from typing import TYPE_CHECKING, Any, Dict, Optional

from hummingbot.connector.derivative.lighter_perpetual import (
    lighter_perpetual_constants as CONSTANTS,
    lighter_perpetual_web_utils as web_utils,
)
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import (
        LighterPerpetualDerivative,
    )


class LighterPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: AuthBase,
        connector: "LighterPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__()
        self._auth = auth
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._ws_assistant = None

    @property
    def last_recv_time(self) -> float:
        if self._ws_assistant is None:
            return 0
        return self._ws_assistant.last_recv_time

    async def _connected_websocket_assistant(self) -> WSAssistant:
        # The connector resolves the account index and builds the authenticated web-assistants
        # factory lazily. Ensure that has happened and (re)bind to the connector's current
        # factory before creating the assistant, so the private subscribe messages carry a
        # valid `auth` token. Otherwise Lighter rejects them with "auth field is required".
        await self._connector._ensure_account_ready()
        self._api_factory = self._connector._web_assistants_factory
        self._ws_assistant = await self._api_factory.get_ws_assistant()
        await self._ws_assistant.connect(
            ws_url=web_utils.wss_url(domain=self._domain),
            ping_timeout=CONSTANTS.PRIVATE_WS_PING_INTERVAL,
        )
        return self._ws_assistant

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        account_index = self._connector.account_index
        channels = (
            CONSTANTS.ACCOUNT_ALL_ORDERS_CHANNEL,
            CONSTANTS.ACCOUNT_ALL_TRADES_CHANNEL,
            CONSTANTS.ACCOUNT_ALL_ASSETS_CHANNEL,
            CONSTANTS.ACCOUNT_ALL_POSITIONS_CHANNEL,
        )
        try:
            for channel in channels:
                await websocket_assistant.send(
                    WSJSONRequest(
                        payload={
                            "type": "subscribe",
                            "channel": f"{channel}/{account_index}",
                        },
                        is_auth_required=True,
                    )
                )
            self.logger().info("Subscribed to Lighter private user channels.")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error subscribing to Lighter private streams.")
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        ping_task = asyncio.create_task(self._app_ping_loop(websocket_assistant))
        try:
            async for ws_response in websocket_assistant.iter_messages():
                data = ws_response.data
                if data is None:
                    continue
                if data.get("type") == "ping":
                    await websocket_assistant.send(WSJSONRequest(payload={"type": "pong"}))
                    continue
                await self._process_event_message(event_message=data, queue=queue)
        finally:
            ping_task.cancel()

    async def _app_ping_loop(self, websocket_assistant: WSAssistant):
        while True:
            try:

                await asyncio.sleep(CONSTANTS.PRIVATE_WS_PING_INTERVAL)
                await websocket_assistant.send(WSJSONRequest(payload={"type": "ping"}))
            except asyncio.CancelledError:
                raise
            except Exception:
                pass

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if event_message.get("error") is not None:
            raise IOError(f"Lighter private websocket error: {event_message['error']}")

        channel = str(event_message.get("channel", ""))
        prefixes = (
            f"{CONSTANTS.ACCOUNT_ALL_ORDERS_CHANNEL}:",
            f"{CONSTANTS.ACCOUNT_ALL_TRADES_CHANNEL}:",
            f"{CONSTANTS.ACCOUNT_ALL_ASSETS_CHANNEL}:",
            f"{CONSTANTS.ACCOUNT_ALL_POSITIONS_CHANNEL}:",
        )
        if channel.startswith(prefixes):
            queue.put_nowait(event_message)
