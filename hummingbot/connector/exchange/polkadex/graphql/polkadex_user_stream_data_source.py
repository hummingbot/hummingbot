from typing import List

from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class PolkadexUserStreamDataSource(UserStreamTrackerDataSource):

    def __init__(self, trading_pairs: List[str]):
        super().__init__()
        self._trading_pairs = trading_pairs

    async def _connected_websocket_assistant(self) -> WSAssistant:
        pass

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        pass
