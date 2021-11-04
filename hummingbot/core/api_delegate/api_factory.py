from typing import List, Optional

from hummingbot.core.api_delegate.connections.connections_factory import ConnectionsFactory
from hummingbot.core.api_delegate.rest_assistant import RESTAssistant
from hummingbot.core.api_delegate.rest_post_processors import RESTPostProcessorBase
from hummingbot.core.api_delegate.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.api_delegate.ws_assistant import WSAssistant


class APIFactory:
    def __init__(
        self,
        rest_pre_processors: Optional[List[RESTPreProcessorBase]] = None,
        rest_post_processors: Optional[List[RESTPostProcessorBase]] = None,
    ):
        self._connections_factory = ConnectionsFactory()
        self._rest_pre_processors = rest_pre_processors or []
        self._rest_post_processors = rest_post_processors or []

    async def get_rest_delegate(self) -> RESTAssistant:
        connection = await self._connections_factory.get_rest_connection()
        delegate = RESTAssistant(
            connection, self._rest_pre_processors, self._rest_post_processors
        )
        return delegate

    async def get_ws_delegate(self) -> WSAssistant:
        connection = await self._connections_factory.get_ws_connection()
        delegate = WSAssistant(connection)
        return delegate
