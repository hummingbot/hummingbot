import types
from typing import Any

from hummingbot.core.web_assistant.connections.data_types import RESTResponse
from hummingbot.core.web_assistant.rest_post_processors import RESTPostProcessorBase


class HotbitRESTPostProcessorBase(RESTPostProcessorBase):
    """An interface class that enables functionality injection into the `RESTAssistant`.

    The logic provided by a class implementing this interface is applied to a response
    before it is returned to the caller.
    """

    async def post_process(self, response: RESTResponse) -> RESTResponse:
        async def json(self) -> Any:
            json_ = await self._aiohttp_response.json(content_type=None)
            return json_

        response.json = types.MethodType(json, response)
        return response
