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

        request.headers = {"Authentication": self.auth_header}
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. Bloxroute does not use this
        functionality
        """

        return request  # pass-through
