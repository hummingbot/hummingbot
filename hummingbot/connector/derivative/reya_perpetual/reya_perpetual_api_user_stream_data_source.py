import asyncio
from typing import Any, Dict

from hummingbot.connector.derivative.reya_perpetual import (
    reya_perpetual_constants as CONSTANTS,
    reya_perpetual_web_utils as web_utils,
)
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

# Wallet channels are public reads; order entry is what requires a signature.
WALLET_CHANNELS = ("orderChanges", "perpExecutions", "positions", "accountSummaries")


class ReyaPerpetualAPIUserStreamDataSource(UserStreamTrackerDataSource):
    def __init__(self, wallet_address: str, api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__()
        self._wallet = wallet_address.lower()
        self._api_factory = api_factory
        self._domain = domain

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=web_utils.wss_url(self._domain))
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        try:
            for resource in WALLET_CHANNELS:
                await websocket_assistant.send(WSJSONRequest(payload={
                    "type": "subscribe", "channel": f"/v2/wallet/{self._wallet}/{resource}",
                }))
            self.logger().info("Subscribed to private order, execution, position and account channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to user streams...")
            raise

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if event_message.get("type") in ("subscribed", "channel_data", "error"):
            queue.put_nowait(event_message)
