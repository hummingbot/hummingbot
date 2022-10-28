from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class PolkadexAuth(AuthBase):

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        raise NotImplementedError

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request
