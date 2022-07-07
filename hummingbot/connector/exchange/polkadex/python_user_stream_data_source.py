import datetime

from hummingbot.connector.exchange.polkadex import polkadex_constants as CONSTANTS
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class PolkadexUserStreamData(UserStreamTrackerDataSource):

    def __init__(self, api_factory: WebAssistantsFactory, endpoint: str):
        super().__init__()
        self._api_factory = api_factory
        self.enclave_endpoint = endpoint
        self._last_recv_time: float = datetime.datetime.now().timestamp()

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._get_ws_assistant()
        print("Connecting to enclave endpoint....")
        await ws.connect(ws_url=self.enclave_endpoint, ping_timeout=CONSTANTS.WS_PING_INTERVAL)
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        print("Trying to subscribe to channels...")
        pass

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        if not self._data_source:
            self._data_source = PolkadexUserStreamData(
                self._api_factory,
                self.enclave_endpoint
            )
        return self._data_source
