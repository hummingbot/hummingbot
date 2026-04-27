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

        # Subscribe only to the proven valid spot private channel.
        # Current spot environments reject account_all_assets with "Invalid Channel".
        account_identifiers = {
            str(self._auth.user_wallet_public_key),
            str(getattr(self._connector, "account_index", "") or ""),
            str(getattr(self._connector, "api_key_index", "") or ""),
        }
        account_identifiers.discard("")

        private_channels = (
            CONSTANTS.WS_ACCOUNT_ALL_CHANNEL,
        )

        sent_channels: set = set()
        for account_identifier in account_identifiers:
            # Lighter spot uses colon-delimited channel names (e.g. account_all:693751).
            # The slash format (account_all/693751) is rejected with "Invalid Channel".
            for base_channel in private_channels:
                channel = f"{base_channel}:{account_identifier}"
                if channel in sent_channels:
                    continue
                await websocket_assistant.send(WSJSONRequest({
                    "type": "subscribe",
                    "channel": channel,
                }))
                sent_channels.add(channel)

        self.logger().info(
            "Subscribed to spot private channels=%s for identifiers=%s (%d subscriptions)",
            list(private_channels),
            sorted(account_identifiers),
            len(sent_channels),
        )

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data
            if data.get("type") == "ping":
                await websocket_assistant.send(WSJSONRequest(payload={"type": "pong"}))
                continue
            await self._process_event_message(event_message=data, queue=queue)

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if event_message.get("error") is not None:
            err_msg = event_message.get("error", {}).get("message", event_message.get("error"))
            if "invalid channel" in str(err_msg).lower():
                self.logger().debug("Ignoring late 'Invalid Channel' response from server: %s", err_msg)
                return
            raise IOError({
                "label": "WSS_ERROR",
                "message": f"Error received via websocket - {err_msg}.",
            })

        message_type = str(event_message.get("type", ""))
        channel = str(event_message.get("channel", ""))
        event_type_name = message_type.split("/", 1)[1] if "/" in message_type else message_type
        account_channels = (
            CONSTANTS.WS_ACCOUNT_ALL_CHANNEL,
        )
        if (
            event_type_name in account_channels
            or any(message_type.endswith(f"/{account_channel}") for account_channel in account_channels)
            or any(channel.startswith(f"{account_channel}/") for account_channel in account_channels)
            or any(channel.startswith(f"{account_channel}:") for account_channel in account_channels)
            or channel in account_channels
        ):
            queue.put_nowait(event_message)
