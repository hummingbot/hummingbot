from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class LighterPerpetualAuth(AuthBase):
    def __init__(self, api_key: str, api_secret: str = "", account_identifier: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret
        self.user_wallet_public_key = account_identifier

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        headers = dict(request.headers or {})
        headers["accept"] = "application/json"
        headers["Content-Type"] = "application/json"
        # Do not expose the API key or index in headers — auth token is used
        # for restricted endpoints via 'auth' query param; public endpoints need no key header.
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request
