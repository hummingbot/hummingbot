import asyncio
from typing import Any, Dict, List, Optional

from hummingbot.connector.derivative.decibel_perpetual import decibel_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger


class DecibelPerpetualAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth,
        trading_pairs: List[str],
        connector,
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._auth = auth
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws = await self._api_factory.get_ws_assistant()
        await ws.connect(
            ws_url=CONSTANTS.WS_URLS[self._domain],
            ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL,
            ws_headers=self._auth.ws_headers,
        )
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        account_addr = self._connector.account_address
        topics = [
            f"{CONSTANTS.WS_ORDER_UPDATES_PREFIX}:{account_addr}",
            f"{CONSTANTS.WS_ACCOUNT_OPEN_ORDERS_PREFIX}:{account_addr}",
            f"{CONSTANTS.WS_USER_TRADES_PREFIX}:{account_addr}",
            f"{CONSTANTS.WS_ACCOUNT_POSITIONS_PREFIX}:{account_addr}",
            f"{CONSTANTS.WS_ACCOUNT_OVERVIEW_PREFIX}:{account_addr}",
        ]
        for topic in topics:
            await ws.send(WSJSONRequest(payload={"method": "subscribe", "topic": topic}))

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data
            if isinstance(data, dict) and data.get("success") is False:
                # subscription error
                self.logger().warning(f"Decibel WS error: {data}")
                continue
            await self._message_queue.put(data)

    async def listen_for_user_stream(self, output: asyncio.Queue):
        ws: Optional[WSAssistant] = None
        while True:
            try:
                ws = await self._connected_websocket_assistant()
                await self._subscribe_channels(ws)
                await self._process_websocket_messages(ws)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error while listening to Decibel user stream. Retrying...")
            finally:
                if ws is not None:
                    await ws.disconnect()
