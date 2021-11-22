import aiohttp
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, RESTResponse


class RESTConnection:
    def __init__(self, aiohttp_client_session: aiohttp.ClientSession):
        self._client_session = aiohttp_client_session

    async def call(self, request: RESTRequest) -> RESTResponse:
        if request.data:
            aiohttp_resp = await self._client_session.request(
                method=request.method.value,
                url=request.url,
                params=request.params,
                data=request.data,
                headers=request.headers,
            )
        else:
            # Remove data field since it might affect how the signature is validated on the server
            aiohttp_resp = await self._client_session.request(
                method=request.method.value,
                url=request.url,
                params=request.params,
                headers=request.headers,
            )
        resp = await self._build_resp(aiohttp_resp)
        return resp

    @staticmethod
    async def _build_resp(aiohttp_resp: aiohttp.ClientResponse) -> RESTResponse:
        resp = RESTResponse(aiohttp_resp)
        return resp
