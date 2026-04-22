import asyncio
from typing import TYPE_CHECKING, Any, Dict, Optional

from hummingbot.connector.exchange.lighter import lighter_constants as CONSTANTS, lighter_web_utils as web_utils
from hummingbot.connector.exchange.lighter.lighter_auth import LighterAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSResponse
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.lighter.lighter_exchange import LighterExchange


class LighterAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        connector: "LighterExchange",
        api_factory: WebAssistantsFactory,
        auth: LighterAuth,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._connector = connector
        self._api_factory = api_factory
        self._auth = auth
        self._domain = domain
        self._ping_task: Optional[asyncio.Task] = None

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        ws_headers = {}
        if self._connector.rest_api_key:
            ws_headers["X-Api-Key"] = self._connector.rest_api_key
        await ws.connect(
            ws_url=web_utils.wss_url(self._domain),
            ws_headers=ws_headers,
            ping_timeout=CONSTANTS.WS_PING_INTERVAL,
        )
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant) -> None:
        response: Optional[WSResponse] = await websocket_assistant.receive()
        message: Dict[str, Any] = response.data if response is not None else {}
        if message.get("type") != "connected":
            raise IOError("Private websocket connection did not acknowledge the session")

        account_all_payload = {
            "type": "subscribe",
            "channel": f"{CONSTANTS.WS_ACCOUNT_ALL_CHANNEL}/{self._auth.user_wallet_public_key}",
        }
        await websocket_assistant.send(WSJSONRequest(account_all_payload))

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data
            if data.get("type") == "ping":
                await websocket_assistant.send(WSJSONRequest(payload={"type": "pong"}))
                continue
            await self._process_event_message(event_message=data, queue=queue)

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        message_type = event_message.get("type")
        channel = str(event_message.get("channel", ""))
        if message_type in {"subscribed/account_all", "update/account_all"} or channel.startswith(f"{CONSTANTS.WS_ACCOUNT_ALL_CHANNEL}:"):
            queue.put_nowait(event_message)
