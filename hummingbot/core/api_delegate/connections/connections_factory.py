import aiohttp
from hummingbot.core.api_delegate.connections.rest_connection import RESTConnection
from hummingbot.core.api_delegate.connections.ws_connection import WSConnection


class ConnectionsFactory:
    def __init__(self):
        self._shared_client = aiohttp.ClientSession()

    def __del__(self):
        self._shared_client.close()

    async def get_rest_connection(self) -> RESTConnection:
        connection = RESTConnection(aiohttp_client_session=self._shared_client)
        return connection

    async def get_ws_connection(self) -> WSConnection:
        connection = WSConnection(aiohttp_client_session=self._shared_client)
        return connection
