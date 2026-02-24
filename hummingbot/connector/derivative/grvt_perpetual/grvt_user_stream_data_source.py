import asyncio
from typing import TYPE_CHECKING, List, Optional

import hummingbot.connector.derivative.grvt_perpetual.grvt_constants as CONSTANTS
import hummingbot.connector.derivative.grvt_perpetual.grvt_web_utils as web_utils
from hummingbot.connector.derivative.grvt_perpetual.grvt_auth import GrvtAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.grvt_perpetual.grvt_derivative import GrvtDerivative


class GrvtUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: GrvtAuth,
        trading_pairs: List[str],
        connector: "GrvtDerivative",
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
        await ws.connect(ws_url=web_utils.wss_url(self._domain), ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
        auth_request = WSJSONRequest(payload={"op": "auth"}, is_auth_required=True)
        auth_request = await self._auth.ws_authenticate(auth_request)
        await ws.send(auth_request)
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        channels = [
            CONSTANTS.WS_ACCOUNT_CHANNEL,
            CONSTANTS.WS_ORDERS_CHANNEL,
            CONSTANTS.WS_FILLS_CHANNEL,
            CONSTANTS.WS_POSITIONS_CHANNEL,
        ]
        for trading_pair in self._trading_pairs:
            symbol = await self._to_exchange_symbol(trading_pair)
            channels.extend(
                [
                    f"{CONSTANTS.WS_ORDERS_CHANNEL}:{symbol}",
                    f"{CONSTANTS.WS_FILLS_CHANNEL}:{symbol}",
                    f"{CONSTANTS.WS_POSITIONS_CHANNEL}:{symbol}",
                ]
            )
        await websocket_assistant.send(WSJSONRequest(payload={"method": "subscribe", "channels": channels}))

    async def _to_exchange_symbol(self, trading_pair: str) -> str:
        symbol = self._connector.exchange_symbol_associated_to_pair(trading_pair)
        if asyncio.iscoroutine(symbol):
            symbol = await symbol
        return str(symbol)
