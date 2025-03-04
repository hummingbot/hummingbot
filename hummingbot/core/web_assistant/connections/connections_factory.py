from typing import TypeVar

import aiohttp

from hummingbot.core.web_assistant.connections.rest_connection import RESTConnection
from hummingbot.core.web_assistant.connections.ws_connection import WSConnection

ConnectionsFactoryT = TypeVar("ConnectionsFactoryT", bound="ConnectionsFactory")


class ConnectionsFactory:
    """This class is a thin wrapper around the underlying REST and WebSocket third-party library.

    The purpose of the class is to isolate the general `web_assistant` infrastructure from the underlying library
    (in this case, `aiohttp`) to enable dependency change with minimal refactoring of the code.

    Note: One future possibility is to enable injection of a specific connection factory implementation in the
    `WebAssistantsFactory` to accommodate cases such as Bittrex that uses a specific WebSocket technology requiring
    a separate third-party library. In that case, a factory can be created that returns `RESTConnection`s using
    `aiohttp` and `WSConnection`s using `signalr_aio`.
    """
    _instance: ConnectionsFactoryT | None = None
    _ws_independent_session: aiohttp.ClientSession | None = None
    _shared_client: aiohttp.ClientSession | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_rest_connection(self) -> RESTConnection:
        """
        Get a REST connection using a shared aiohttp.ClientSession.
        """
        client = await self._get_shared_client()
        return RESTConnection(aiohttp_client_session=client)

    async def get_ws_connection(self) -> WSConnection:
        """
        Get a WebSocket connection using either the independent session (if set)
        or the shared client.
        """
        client = self._ws_independent_session or await self._get_shared_client()
        return WSConnection(aiohttp_client_session=client)

    async def _get_shared_client(self) -> aiohttp.ClientSession:
        """
        Lazily create a shared aiohttp.ClientSession if not already available.
        """
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def close(self) -> None:
        """
        Close any open aiohttp.ClientSession instances.
        """
        if self._shared_client is not None:
            await self._shared_client.close()
            self._shared_client = None
        if self._ws_independent_session is not None:
            await self._ws_independent_session.close()
            self._ws_independent_session = None

    async def __aenter__(self) -> ConnectionsFactoryT:
        """
        Enter the async context manager.
        """
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Exit the async context manager by closing client sessions.
        """
        await self.close()
