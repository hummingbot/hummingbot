from typing import Optional

import aiohttp
from hummingbot.core.web_assistant.connections.rest_connection import RESTConnection
from hummingbot.core.web_assistant.connections.ws_connection import WSConnection


class ConnectionsFactory:
    def __init__(self):
        self._shared_client: Optional[aiohttp.ClientSession] = None

    async def get_rest_connection(self) -> RESTConnection:
        shared_client = await self._get_shared_client()
        connection = RESTConnection(aiohttp_client_session=shared_client)
        return connection

    async def get_ws_connection(self) -> WSConnection:
        shared_client = await self._get_shared_client()
        connection = WSConnection(aiohttp_client_session=shared_client)
        return connection

    async def _get_shared_client(self) -> aiohttp.ClientSession:
        self._shared_client = self._shared_client or aiohttp.ClientSession()
        return self._shared_client
