from typing import List, Optional

from hummingbot.core.api_throttler.async_throttler_base import AsyncThrottlerBase
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.connections_factory import ConnectionsFactory
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.rest_post_processors import RESTPostProcessorBase
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.core.web_assistant.ws_post_processors import WSPostProcessorBase
from hummingbot.core.web_assistant.ws_pre_processors import WSPreProcessorBase


class WebAssistantsFactory:
    """Creates `RESTAssistant` and `WSAssistant` objects.

    The purpose of the `web_assistant` layer is to abstract away all WebSocket and REST operations from the exchange
    logic. The assistant objects are designed to be injectable with additional logic via the pre- and post-processor
    lists. Consult the documentation of the relevant assistant and/or pre-/post-processor class for
    additional information.

    todo: integrate AsyncThrottler
    """
    def __init__(
        self,
        throttler: AsyncThrottlerBase,
        rest_pre_processors: Optional[List[RESTPreProcessorBase]] = None,
        rest_post_processors: Optional[List[RESTPostProcessorBase]] = None,
        ws_pre_processors: Optional[List[WSPreProcessorBase]] = None,
        ws_post_processors: Optional[List[WSPostProcessorBase]] = None,
        auth: Optional[AuthBase] = None,
    ):
        self._connections_factory = ConnectionsFactory()
        self._rest_pre_processors = rest_pre_processors or []
        self._rest_post_processors = rest_post_processors or []
        self._ws_pre_processors = ws_pre_processors or []
        self._ws_post_processors = ws_post_processors or []
        self._auth = auth
        self._throttler = throttler

    @property
    def throttler(self) -> AsyncThrottlerBase:
        return self._throttler

    @property
    def auth(self) -> Optional[AuthBase]:
        return self._auth

    async def get_rest_assistant(self) -> RESTAssistant:
        connection = await self._connections_factory.get_rest_connection()
        assistant = RESTAssistant(
            connection=connection,
            throttler=self._throttler,
            rest_pre_processors=self._rest_pre_processors,
            rest_post_processors=self._rest_post_processors,
            auth=self._auth
        )
        return assistant

    async def get_ws_assistant(self) -> WSAssistant:
        connection = await self._connections_factory.get_ws_connection()
        assistant = WSAssistant(
            connection, self._ws_pre_processors, self._ws_post_processors, self._auth
        )
        return assistant
