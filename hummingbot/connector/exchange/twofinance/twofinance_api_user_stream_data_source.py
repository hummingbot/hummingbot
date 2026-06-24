import asyncio
from typing import Optional

from hummingbot.connector.exchange.twofinance import (
    twofinance_constants as CONSTANTS,
    twofinance_web_utils as web_utils,
)
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class TwoFinanceAPIUserStreamDataSource(UserStreamTrackerDataSource):
    def __init__(
        self,
        api_factory: WebAssistantsFactory,
        auth_headers: dict[str, str],
        engine_id: str,
        wallet_id: int,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        ws_url: Optional[str] = None,
    ):
        super().__init__()
        self._api_factory = api_factory
        self._auth_headers = auth_headers
        self._engine_id = engine_id
        self._wallet_id = wallet_id
        self._domain = domain
        self._ws_url = ws_url

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws = await self._api_factory.get_ws_assistant()
        await ws.connect(
            ws_url=web_utils.wss_url(self._domain, self._ws_url),
            ws_headers=self._auth_headers,
            ping_timeout=30,
        )
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        await websocket_assistant.send(
            WSJSONRequest(
                payload={
                    "type": CONSTANTS.WS_PRIVATE_SUBSCRIBE,
                    "channels": ["orders", "trades", "balances"],
                    "engine_id": self._engine_id,
                    "wallet_id": self._wallet_id,
                },
                is_auth_required=False,
            )
        )

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data
            if isinstance(data, dict):
                queue.put_nowait(data)
