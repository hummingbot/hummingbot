from typing import Optional

import aiohttp

from hummingbot.core.web_assistant.connections.rest_connection import RESTConnection
from hummingbot.core.web_assistant.connections.ws_connection import WSConnection


class ConnectionsFactory:
    """This class is a thin wrapper around the underlying REST and WebSocket third-party library.

    The purpose of the class is to isolate the general `web_assistant` infrastructure from the underlying library
    (in this case, `aiohttp`) to enable dependency change with minimal refactoring of the code.

    Note: One future possibility is to enable injection of a specific connection factory implementation in the
    `WebAssistantsFactory` to accommodate cases such as Bittrex that uses a specific WebSocket technology requiring
    a separate third-party library. In that case, a factory can be created that returns `RESTConnection`s using
    `aiohttp` and `WSConnection`s using `signalr_aio`.
    """

    def __init__(self):
        # _ws_independent_session is intended to be used only in unit tests
        self._ws_independent_session: Optional[aiohttp.ClientSession] = None

        self._shared_client: Optional[aiohttp.ClientSession] = None

    async def get_rest_connection(self) -> RESTConnection:
        shared_client = await self._get_shared_client()
        connection = RESTConnection(aiohttp_client_session=shared_client)
        return connection

    async def get_ws_connection(self) -> WSConnection:
        shared_client = self._ws_independent_session or await self._get_shared_client()
        connection = WSConnection(aiohttp_client_session=shared_client)
        return connection

    async def _get_shared_client(self) -> aiohttp.ClientSession:
        self._shared_client = self._shared_client or aiohttp.ClientSession()
        return self._shared_client
