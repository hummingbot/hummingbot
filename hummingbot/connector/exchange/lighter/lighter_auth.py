from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class LighterAuth(AuthBase):
    def __init__(self, api_key: str, api_secret: str = "", account_identifier: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret
        self.user_wallet_public_key = account_identifier

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        headers = dict(request.headers or {})
        headers["accept"] = "application/json"
        headers["Content-Type"] = "application/json"
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        request.headers = headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request
