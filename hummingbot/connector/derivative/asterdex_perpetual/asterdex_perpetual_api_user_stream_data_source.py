import asyncio
import logging
from typing import Any, Dict, List, Optional

from hummingbot.connector.derivative.asterdex_perpetual import asterdex_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.asterdex_perpetual.asterdex_perpetual_auth import AsterdexPerpetualAuth
from hummingbot.connector.derivative.asterdex_perpetual.asterdex_perpetual_derivative import AsterdexPerpetualDerivative
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.connections.data_types import WSAssistant
from hummingbot.logger import HummingbotLogger


class AsterdexPerpetualAPIUserStreamDataSource(UserStreamTrackerDataSource):
    def __init__(
        self,
        auth: AsterdexPerpetualAuth,
        trading_pairs: List[str],
        connector: AsterdexPerpetualDerivative,
        api_factory: WebAssistantsFactory,
    ):
        super().__init__()
        self._auth = auth
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._api_factory = api_factory
        self._logger = HummingbotLogger.get_logger()

    @property
    def name(self) -> str:
        return "asterdex_perpetual"

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """Create authenticated websocket connection"""
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.WS_URL)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        """Subscribe to user stream channels"""
        pass

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        """Process websocket messages"""
        while True:
            try:
                async for ws_message in websocket_assistant.iter_messages():
                    if ws_message.type == "text":
                        data = ws_message.data
                        await queue.put(data)
            except Exception as e:
                self._logger.error(f"Error processing user stream message: {e}")
                await asyncio.sleep(1)

    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """Listen for user stream events"""
        while True:
            try:
                ws = await self._connected_websocket_assistant()
                await self._subscribe_channels(ws)
                await self._process_websocket_messages(ws, output)
            except Exception as e:
                self._logger.error(f"Error in user stream listener: {e}")
                await asyncio.sleep(5)
