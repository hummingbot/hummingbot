from hummingbot.connector.exchange.latoken.latoken_ws_connection import LatokenWSConnection
from hummingbot.core.web_assistant.connections.connections_factory import ConnectionsFactory


class LatokenConnectionsFactory(ConnectionsFactory):
    async def get_ws_connection(self) -> LatokenWSConnection:
        shared_client = await self._get_shared_client()
        connection = LatokenWSConnection(aiohttp_client_session=shared_client)
        return connection
