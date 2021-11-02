from typing import List, Optional

from hummingbot.core.api_delegate.connections.connections_base import ConnectionsFactoryBase
from hummingbot.core.api_delegate.connections.connections_factory import ConnectionsFactory
from hummingbot.core.api_delegate.rest_delegate import RESTDelegate
from hummingbot.core.api_delegate.rest_post_processors import RESTPostProcessorBase
from hummingbot.core.api_delegate.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.api_delegate.ws_delegate import WSDelegate


class APIFactory:
    def __init__(
        self,
        connections_factory: Optional[ConnectionsFactoryBase] = None,
        rest_pre_processors: Optional[List[RESTPreProcessorBase]] = None,
        rest_post_processors: Optional[List[RESTPostProcessorBase]] = None,
    ):
        self._connections_factory = connections_factory or ConnectionsFactory()
        self._rest_pre_processors = rest_pre_processors or []
        self._rest_post_processors = rest_post_processors or []

    async def get_rest_delegate(self) -> RESTDelegate:
        connection = await self._connections_factory.get_rest_connection()
        delegate = RESTDelegate(
            connection, self._rest_pre_processors, self._rest_post_processors
        )
        return delegate

    async def get_ws_delegate(self) -> WSDelegate:
        connection = await self._connections_factory.get_ws_connection()
        delegate = WSDelegate(connection)
        return delegate
