import asyncio
from typing import TYPE_CHECKING, List

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

    async def listen_for_user_stream(self, output: asyncio.Queue):
        #  Polkadex doesn't need this.
        pass
