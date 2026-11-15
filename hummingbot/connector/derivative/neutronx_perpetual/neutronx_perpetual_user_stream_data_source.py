import asyncio
from typing import TYPE_CHECKING

from neutronx_sdk.indexer import CHANNEL_FILLS, CHANNEL_ORDERS, CHANNEL_POSITIONS

from hummingbot.connector.derivative.neutronx_perpetual.data_sources import indexer_stream
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.derivative.neutronx_perpetual.neutronx_perpetual_derivative import (
        NeutronxPerpetualDerivative,
    )

OWNER_CHANNELS = (CHANNEL_ORDERS, CHANNEL_FILLS, CHANNEL_POSITIONS)


class NeutronxPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    def __init__(self, connector: "NeutronxPerpetualDerivative", api_factory: WebAssistantsFactory) -> None:
        super().__init__()
        self._connector = connector
        self._api_factory = api_factory

    async def _connected_websocket_assistant(self) -> WSAssistant:
        return await indexer_stream.connect(self._api_factory, self._connector.network, self._connector.api_key)

    async def _subscribe_channels(self, websocket_assistant: WSAssistant) -> None:
        owner = self._connector.account_address
        await indexer_stream.subscribe(websocket_assistant, [(channel, owner) for channel in OWNER_CHANNELS])

    async def _send_ping(self, websocket_assistant: WSAssistant) -> None:
        await indexer_stream.send_ping(websocket_assistant)

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue) -> None:
        async with indexer_stream.heartbeat(websocket_assistant):
            async for response in websocket_assistant.iter_messages():
                message = response.data
                if not isinstance(message, dict):
                    continue
                frame = indexer_stream.parse_frame(message, self.logger())
                if frame.is_data and frame.channel in OWNER_CHANNELS:
                    queue.put_nowait(message)
