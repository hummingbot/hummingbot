from typing import List, Optional

from hummingbot.connector.exchange.latoken.latoken_connections_factory import LatokenConnectionsFactory
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.rest_post_processors import RESTPostProcessorBase
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_post_processors import WSPostProcessorBase
from hummingbot.core.web_assistant.ws_pre_processors import WSPreProcessorBase


class LatokenWebAssistantsFactory(WebAssistantsFactory):
    def __init__(self, rest_pre_processors: Optional[List[RESTPreProcessorBase]] = None,
                 rest_post_processors: Optional[List[RESTPostProcessorBase]] = None,
                 ws_pre_processors: Optional[List[WSPreProcessorBase]] = None,
                 ws_post_processors: Optional[List[WSPostProcessorBase]] = None, auth: Optional[AuthBase] = None):
        self._connections_factory = LatokenConnectionsFactory()
        self._rest_pre_processors = rest_pre_processors or []
        self._rest_post_processors = rest_post_processors or []
        self._ws_pre_processors = ws_pre_processors or []
        self._ws_post_processors = ws_post_processors or []
        self._auth = auth
