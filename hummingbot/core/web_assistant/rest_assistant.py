from copy import deepcopy
from typing import List, Optional

from hummingbot.core.web_assistant.connections.rest_connection import RESTConnection
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, RESTResponse
from hummingbot.core.web_assistant.rest_post_processors import RESTPostProcessorBase
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase


class RESTAssistant:
    def __init__(
        self,
        connection: RESTConnection,
        rest_pre_processors: Optional[List[RESTPreProcessorBase]] = None,
        rest_post_processors: Optional[List[RESTPostProcessorBase]] = None,
    ):
        self._connection = connection
        self._rest_pre_processors = rest_pre_processors or []
        self._rest_post_processors = rest_post_processors or []

    async def call(self, request: RESTRequest) -> RESTResponse:
        request = deepcopy(request)
        request = await self._pre_process_request(request)
        resp = await self._connection.call(request)
        resp = await self._post_process_response(resp)
        return resp

    async def _pre_process_request(self, request: RESTRequest) -> RESTRequest:
        for pre_processor in self._rest_pre_processors:
            request = await pre_processor.pre_process(request)
        return request

    async def _post_process_response(self, response: RESTResponse) -> RESTResponse:
        for post_processor in self._rest_post_processors:
            response = await post_processor.post_process(response)
        return response
