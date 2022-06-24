import asyncio
from typing import List

from hummingbot.connector.gateway.clob import clob_constants as constant
from hummingbot.connector.gateway.clob.clob_auth import CLOBAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class CLOBAPIUserStreamDataSource(UserStreamTrackerDataSource):

    def __init__(
        self,
        auth: CLOBAuth,
        trading_pairs: List[str],
        connector: constant.DEFAULT_CONNECTOR,
        api_factory: WebAssistantsFactory,
        domain: str = constant.DEFAULT_DOMAIN
    ):
        super().__init__()
        self._auth: CLOBAuth = auth
        self._current_listen_key = None
        self._domain = domain
        self._api_factory = api_factory

        self._listen_key_initialized_event: asyncio.Event = asyncio.Event()
        self._last_listen_key_ping_ts = 0

    async def _connected_websocket_assistant(self) -> WSAssistant:
        # TODO do we need to override this method?!!!
        raise NotImplementedError

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        # TODO do we need to override this method?!!!
        raise NotImplementedError
