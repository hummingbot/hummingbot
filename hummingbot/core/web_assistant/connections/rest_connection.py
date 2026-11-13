import aiohttp

from hummingbot.core.web_assistant.connections.data_types import RESTRequest, RESTResponse

# aiohttp raises this when a pooled keep-alive connection was closed by the server after the
# pool handed it out and before the request body was written. The request never left the client,
# so sending it again on a fresh connection is safe for every method, including order creation.
# Older aiohttp versions (3.8-3.9) raise the same condition as ClientOSError with this message.
_CONNECTION_RESET_ERROR = getattr(aiohttp, "ClientConnectionResetError", aiohttp.ClientOSError)
_CLOSING_TRANSPORT_MESSAGE = "Cannot write to closing transport"


class RESTConnection:
    def __init__(self, aiohttp_client_session: aiohttp.ClientSession):
        self._client_session = aiohttp_client_session

    async def call(self, request: RESTRequest) -> RESTResponse:
        try:
            aiohttp_resp = await self._request(request)
        except _CONNECTION_RESET_ERROR as e:
            if not (self._request_never_left(e) and self._body_can_be_sent_again(request)):
                raise
            # the pool will not reuse the closing transport; one retry gets a live connection
            aiohttp_resp = await self._request(request)

        resp = await self._build_resp(aiohttp_resp)
        return resp

    async def _request(self, request: RESTRequest) -> aiohttp.ClientResponse:
        return await self._client_session.request(
            method=request.method.value,
            url=request.url,
            params=request.params,
            data=request.data,
            headers=request.headers,
        )

    @staticmethod
    def _body_can_be_sent_again(request: RESTRequest) -> bool:
        # a str, bytes or dict body is rebuilt from the value on every attempt; a file or an
        # async iterable may already be partly consumed, so those are not retried
        return request.data is None or isinstance(request.data, (str, bytes, dict))

    @staticmethod
    def _request_never_left(error: Exception) -> bool:
        # ClientConnectionResetError is raised only from the writer; on older aiohttp the same
        # failure arrives as a ClientOSError whose text names the closing transport
        if type(error).__name__ == "ClientConnectionResetError":
            return True
        return _CLOSING_TRANSPORT_MESSAGE in str(error)

    @staticmethod
    async def _build_resp(aiohttp_resp: aiohttp.ClientResponse) -> RESTResponse:
        resp = RESTResponse(aiohttp_resp)
        return resp
