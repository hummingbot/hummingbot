import asyncio
import random
from typing import Any, Dict, Optional, Set

from hummingbot.connector.derivative.reya_perpetual import (
    reya_perpetual_constants as CONSTANTS,
    reya_perpetual_web_utils as web_utils,
)
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

# Wallet channels are public reads; order entry is what requires a signature.
WALLET_CHANNELS = ("orderChanges", "perpExecutions", "positions", "accountSummaries", "positionRisk")


class ReyaPerpetualAPIUserStreamDataSource(UserStreamTrackerDataSource):
    def __init__(self, wallet_address: str, api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__()
        self._wallet = wallet_address.lower()
        self._api_factory = api_factory
        self._domain = domain
        self._channels = {f"/v2/wallet/{self._wallet}/{resource}" for resource in WALLET_CHANNELS}
        self._resubscribe_delays: Dict[str, float] = {}
        self._resubscribe_tasks: Set[asyncio.Task] = set()

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=web_utils.wss_url(self._domain))
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        try:
            for resource in WALLET_CHANNELS:
                await self._subscribe(websocket_assistant, f"/v2/wallet/{self._wallet}/{resource}")
            self.logger().info("Subscribed to private order, execution, position and account channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to user streams...")
            raise

    @staticmethod
    async def _subscribe(websocket_assistant: WSAssistant, channel: str):
        await websocket_assistant.send(WSJSONRequest(payload={"type": "subscribe", "channel": channel}))

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        message_type = event_message.get("type")
        if message_type in ("subscribed", "channel_data", "error"):
            queue.put_nowait(event_message)
        channel = event_message.get("channel")
        if channel not in self._channels:
            return
        if message_type == "subscribed":
            self._resubscribe_delays.pop(channel, None)
        elif message_type == "error":
            # Reya ends a subscription it cannot serve, for example while it cannot value an
            # account, and the channel stays silent until it is requested again.
            delay = self._resubscribe_delays.get(channel, CONSTANTS.RESUBSCRIBE_INITIAL_DELAY)
            self._resubscribe_delays[channel] = min(delay * 2, CONSTANTS.RESUBSCRIBE_MAX_DELAY)
            task = asyncio.create_task(self._resubscribe_after_delay(
                self._ws_assistant, channel, delay * random.uniform(1, 1.25)))
            self._resubscribe_tasks.add(task)
            task.add_done_callback(self._resubscribe_tasks.discard)

    async def _resubscribe_after_delay(self, websocket_assistant: Optional[WSAssistant], channel: str, delay: float):
        await self._sleep(delay)
        if websocket_assistant is None or websocket_assistant is not self._ws_assistant:
            return  # The connection was replaced; reconnecting subscribes again.
        try:
            await self._subscribe(websocket_assistant, channel)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().warning(f"Could not resubscribe to {channel}; reconnecting subscribes again.", exc_info=True)

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        for task in list(self._resubscribe_tasks):
            task.cancel()
        self._resubscribe_tasks.clear()
        self._resubscribe_delays.clear()
        await super()._on_user_stream_interruption(websocket_assistant)
