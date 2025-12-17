import ssl
from typing import List, TypeVar

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
    _instance: ConnectionsFactoryT | None = None  # Singleton control

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._ws_independent_session: aiohttp.ClientSession | None = None
            self._shared_client: aiohttp.ClientSession | None = None
            self._disable_tls_1_3: bool = False
            self._clients_to_close: List[aiohttp.ClientSession] = []
            self._initialized = True

    def set_disable_tls_1_3(self, disable: bool) -> None:
        """
        Set the _disable_tls_1_3 flag. If a shared client exists, it will be added to the list of
        clients to close and reset to None so that a new one with the updated settings will be created.

        :param disable: Whether to disable TLS 1.3
        """
        self._disable_tls_1_3 = disable
        if self._shared_client is not None:
            self._clients_to_close.append(self._shared_client)
            self._shared_client = None

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
            if self._disable_tls_1_3:
                # Create SSL context with TLSv1.2 for better VPN compatibility
                ssl_context = ssl.create_default_context()
                ssl_context.options &= ~ssl.OP_NO_TLSv1_2  # Enable TLSv1.2
                ssl_context.options |= ssl.OP_NO_TLSv1_3   # Disable TLSv1.3

                # Create connector with SSL context
                connector = aiohttp.TCPConnector(ssl=ssl_context)
                self._shared_client = aiohttp.ClientSession(connector=connector)
            else:
                # Simple client session construction (original behavior)
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

        # Close any clients that were set aside for closing
        for client in self._clients_to_close:
            await client.close()
        self._clients_to_close.clear()

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
