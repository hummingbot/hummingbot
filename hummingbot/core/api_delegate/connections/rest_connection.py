import aiohttp
from hummingbot.core.api_delegate.connections.connections_base import RESTConnectionBase
from hummingbot.core.api_delegate.data_types import RESTMethod, RESTRequest, RESTResponse


class RESTConnection(RESTConnectionBase):
    def __init__(self, aiohttp_client_session: aiohttp.ClientSession):
        self._client_session = aiohttp_client_session

    async def call(self, request: RESTRequest) -> RESTResponse:
        aiohttp_resp = await self._client_session.request(
            method=request.method.value,
            url=request.url,
            params=request.params,
            data=request.data,
            headers=request.headers,
        )
        resp = await self._build_resp(aiohttp_resp)
        return resp

    @staticmethod
    async def _build_resp(aiohttp_resp: aiohttp.ClientResponse) -> RESTResponse:
        method = RESTMethod[aiohttp_resp.method.upper()]
        body = await aiohttp_resp.read()
        resp = RESTResponse(
            url=str(aiohttp_resp.url),
            method=method,
            status=aiohttp_resp.status,
            body=body,
            headers=aiohttp_resp.headers,
        )
        return resp
