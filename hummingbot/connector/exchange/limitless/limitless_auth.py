"""Limitless auth stub.

Authentication is handled internally by the LimitlessConnector (limitless-sdk).
This class satisfies Hummingbot's AuthBase interface but does not sign requests
itself — all authenticated calls go through the inner connector.
"""

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class LimitlessAuth(AuthBase):

    def __init__(self, api_key: str, private_key: str):
        self._api_key = api_key
        self._private_key = private_key

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        request.headers["X-API-Key"] = self._api_key
        request.headers["Content-Type"] = "application/json"
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request
