from asyncio import wait_for
from copy import deepcopy
from typing import List, Optional

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.rest_connection import RESTConnection
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, RESTResponse
from hummingbot.core.web_assistant.rest_post_processors import RESTPostProcessorBase
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase


class RESTAssistant:
    """A helper class to contain all REST-related logic.

    The class can be injected with additional functionality by passing a list of objects inheriting from
    the `RESTPreProcessorBase` and `RESTPostProcessorBase` classes. The pre-processors are applied to a request
    before it is sent out, while the post-processors are applied to a response before it is returned to the caller.
    """
    def __init__(
        self,
        connection: RESTConnection,
        rest_pre_processors: Optional[List[RESTPreProcessorBase]] = None,
        rest_post_processors: Optional[List[RESTPostProcessorBase]] = None,
        auth: Optional[AuthBase] = None,
    ):
        self._connection = connection
        self._rest_pre_processors = rest_pre_processors or []
        self._rest_post_processors = rest_post_processors or []
        self._auth = auth

    async def call(self, request: RESTRequest, timeout: Optional[float] = None) -> RESTResponse:
        request = deepcopy(request)
        request = await self._pre_process_request(request)
        request = await self._authenticate(request)
        resp = await wait_for(self._connection.call(request), timeout)
        resp = await self._post_process_response(resp)
        return resp

    async def _pre_process_request(self, request: RESTRequest) -> RESTRequest:
        for pre_processor in self._rest_pre_processors:
            request = await pre_processor.pre_process(request)
        return request

    async def _authenticate(self, request: RESTRequest):
        if self._auth is not None and request.is_auth_required:
            request = await self._auth.rest_authenticate(request)
        return request

    async def _post_process_response(self, response: RESTResponse) -> RESTResponse:
        for post_processor in self._rest_post_processors:
            response = await post_processor.post_process(response)
        return response
