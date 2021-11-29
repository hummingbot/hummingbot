from typing import List, Optional

from hummingbot.core.web_assistant.connections.connections_factory import ConnectionsFactory
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.rest_post_processors import RESTPostProcessorBase
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.core.web_assistant.ws_post_processors import WSPostProcessorBase
from hummingbot.core.web_assistant.ws_pre_processors import WSPreProcessorBase


class WebAssistantsFactory:
    def __init__(
        self,
        rest_pre_processors: Optional[List[RESTPreProcessorBase]] = None,
        rest_post_processors: Optional[List[RESTPostProcessorBase]] = None,
        ws_pre_processors: Optional[List[WSPreProcessorBase]] = None,
        ws_post_processors: Optional[List[WSPostProcessorBase]] = None,
    ):
        self._connections_factory = ConnectionsFactory()
        self._rest_pre_processors = rest_pre_processors or []
        self._rest_post_processors = rest_post_processors or []
        self._ws_pre_processors = ws_pre_processors or []
        self._ws_post_processors = ws_post_processors or []

    async def get_rest_assistant(self) -> RESTAssistant:
        connection = await self._connections_factory.get_rest_connection()
        assistant = RESTAssistant(
            connection, self._rest_pre_processors, self._rest_post_processors
        )
        return assistant

    async def get_ws_assistant(self) -> WSAssistant:
        connection = await self._connections_factory.get_ws_connection()
        assistant = WSAssistant(connection, self._ws_pre_processors, self._ws_post_processors)
        return assistant
