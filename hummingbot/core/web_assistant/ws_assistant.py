from copy import deepcopy
from typing import AsyncGenerator, List, Optional

from hummingbot.core.web_assistant.connections.ws_connection import WSConnection
from hummingbot.core.web_assistant.connections.data_types import WSRequest, WSResponse
from hummingbot.core.web_assistant.ws_post_processors import WSPostProcessorBase
from hummingbot.core.web_assistant.ws_pre_processors import WSPreProcessorBase


class WSAssistant:
    def __init__(
        self,
        connection: WSConnection,
        ws_pre_processors: Optional[List[WSPreProcessorBase]] = None,
        ws_post_processors: Optional[List[WSPostProcessorBase]] = None,
    ):
        self._connection = connection
        self._ws_pre_processors = ws_pre_processors or []
        self._ws_post_processors = ws_post_processors or []

    @property
    def last_recv_time(self) -> float:
        return self._connection.last_recv_time

    async def connect(
        self,
        ws_url: str,
        *,
        ping_timeout: float = 10,
        message_timeout: Optional[float] = None,
    ):
        await self._connection.connect(ws_url, ping_timeout, message_timeout)

    async def disconnect(self):
        await self._connection.disconnect()

    async def subscribe(self, request: WSRequest):
        """Will eventually be used to handle automatic re-connection."""
        await self.send(request)

    async def send(self, request: WSRequest):
        request = deepcopy(request)
        request = await self._pre_process_request(request)
        await self._connection.send(request)

    async def iter_messages(self) -> AsyncGenerator[Optional[WSResponse], None]:
        """Will yield None and stop if `WSDelegate.disconnect()` is called while waiting for a response."""
        while self._connection.connected:
            response = await self._connection.receive()
            response = await self._post_process_response(response)
            yield response

    async def receive(self) -> Optional[WSResponse]:
        """Will return None if `WSDelegate.disconnect()` is called while waiting for a response."""
        response = await self._connection.receive()
        if response is not None:
            response = await self._post_process_response(response)
        return response

    async def _pre_process_request(self, request: WSRequest) -> WSRequest:
        for pre_processor in self._ws_pre_processors:
            request = await pre_processor.pre_process(request)
        return request

    async def _post_process_response(self, response: WSResponse) -> WSResponse:
        for post_processor in self._ws_post_processors:
            response = await post_processor.post_process(response)
        return response
