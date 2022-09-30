import aiohttp

from hummingbot.core.web_assistant.connections.data_types import RESTRequest, RESTResponse


class RESTConnection:
    def __init__(self, aiohttp_client_session: aiohttp.ClientSession):
        self._client_session = aiohttp_client_session

    async def call(self, request: RESTRequest) -> RESTResponse:
        async with self._client_session.request(method=str(request.method.value),
                                                url=request.url,
                                                params=request.params,
                                                data=request.data,
                                                headers=request.headers,
                                                ) as aiohttp_resp:
            resp = await RESTResponse().read(aiohttp_resp)
        return resp
