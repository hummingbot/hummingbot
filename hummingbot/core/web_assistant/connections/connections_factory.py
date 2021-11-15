import aiohttp
from hummingbot.core.web_assistant.connections.rest_connection import RESTConnection
from hummingbot.core.web_assistant.connections.ws_connection import WSConnection


class ConnectionsFactory:
    def __init__(self):
        self._shared_client = aiohttp.ClientSession()

    async def get_rest_connection(self) -> RESTConnection:
        connection = RESTConnection(aiohttp_client_session=self._shared_client)
        return connection

    async def get_ws_connection(self) -> WSConnection:
        connection = WSConnection(aiohttp_client_session=self._shared_client)
        return connection
