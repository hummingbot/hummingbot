from typing import Dict

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class BloxrouteOpenbookAuth(AuthBase):
    def __init__(self, auth_header: str):
        self.auth_header = auth_header

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the Bloxroute authentication header to the HTTP request
        """


        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self.authentication_headers(request=request))
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. Bloxroute does not use this
        functionality
        """

        return request  # pass-through

    def authentication_headers(self, request: RESTRequest) -> Dict[str, Any]:
        timestamp = str(int(self.time_provider.time() * 1e3))

        params = json.dumps(request.params) if request.params is not None else request.data

        sign = self._generate_signature(timestamp=timestamp, body=params)

        header = {
            "X-BM-KEY": self.api_key,
            "X-BM-SIGN": sign,
            "X-BM-TIMESTAMP": timestamp,
            "X-BM-BROKER-ID": CONSTANTS.BROKER_ID,
        }

        return header


