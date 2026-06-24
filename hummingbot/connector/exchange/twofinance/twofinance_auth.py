from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class TwoFinanceAuth(AuthBase):
    def __init__(self, bearer_token: str = ""):
        self._bearer_token = bearer_token.strip()

    @property
    def authorization_header(self) -> str:
        if not self._bearer_token:
            return ""
        if self._bearer_token.lower().startswith("bearer "):
            return self._bearer_token
        return f"Bearer {self._bearer_token}"

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        if self.authorization_header:
            headers = dict(request.headers or {})
            headers["Authorization"] = self.authorization_header
            request.headers = headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request
