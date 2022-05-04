from hummingbot.core.web_assistant.connections.data_types import WSRequest
from hummingbot.core.web_assistant.connections.ws_connection import WSConnection


class LatokenWSConnection(WSConnection):
    async def send(self, request: WSRequest):
        self._ensure_connected()
        await self._connection.send_str(request.payload)
