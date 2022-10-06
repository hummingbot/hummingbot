import asyncio
from typing import TYPE_CHECKING, List

from hummingbot.connector.exchange.polkadex import polkadex_constants as CONSTANTS
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.exchange.polkadex.polkadex_exchange import PolkadexExchange


class PolkadexUserStreamDataSource(UserStreamTrackerDataSource):

    @property
    def last_recv_time(self) -> float:
        # TODO: fix this.
        return 1

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        pass

    def __init__(self, trading_pairs: List[str],
                 connector: 'PolkadexExchange',
                 api_factory: WebAssistantsFactory, ):
        super().__init__()
        self._api_factory = api_factory
        self._connector = connector
        self._trading_pairs = trading_pairs

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        print("Connecting to websocket user for user streams: ", self._connector.wss_url)
        await ws.connect(ws_url=self._connector.wss_url, ping_timeout=CONSTANTS.WS_PING_INTERVAL)
        return ws

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def listen_for_user_stream(self, output: asyncio.Queue):
        #  Polkadex doesn't need this.
        pass
